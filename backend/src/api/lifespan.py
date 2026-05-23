from contextlib import asynccontextmanager

from fastapi import FastAPI

import src.api.logging_  # noqa: F401
from src.api.parsers.browser_session_pool import init_browser_session_pool
from src.config import api_settings
from src.db import SQLAlchemyStorage


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage = SQLAlchemyStorage.from_url(api_settings.db_url.get_secret_value())
    app.state.storage = storage
    browser_pool = init_browser_session_pool()
    app.state.browser_pool = browser_pool
    await browser_pool.prewarm()

    try:
        yield
    finally:
        await browser_pool.shutdown()
        await storage.close_connection()

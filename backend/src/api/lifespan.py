import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

import src.api.logging_  # noqa: F401
from src.api.parsers.browser_session_pool import init_browser_session_pool
from src.api.parsers.proxy_bridge import bridge_manager
from src.config import api_settings
from src.db import SQLAlchemyStorage

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage = SQLAlchemyStorage.from_url(api_settings.db_url.get_secret_value())
    app.state.storage = storage
    browser_pool = init_browser_session_pool()
    app.state.browser_pool = browser_pool
    try:
        await browser_pool.prewarm()
    except Exception as exc:
        logger.error(
            "Browser pool prewarm failed (API will start; first scrape may retry): %s",
            exc,
        )

    try:
        yield
    finally:
        await browser_pool.shutdown()
        await bridge_manager.shutdown_all()
        await storage.close_connection()

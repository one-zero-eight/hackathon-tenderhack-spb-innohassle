from __future__ import annotations

import asyncio
import logging

from src.api.parsers.ozon.parser import OzonSeleniumParser
from src.api.parsers.wildberries.parser import WildberriesSeleniumParser
from src.config import ozon_settings, settings_dir, wildberries_settings

logger = logging.getLogger(__name__)


class BrowserSessionPool:
    """Держит Chrome WB/Ozon между запросами — без холодного старта на каждый /prices/search."""

    def __init__(self) -> None:
        self._wb: WildberriesSeleniumParser | None = None
        self._ozon: OzonSeleniumParser | None = None
        self._wb_lock = asyncio.Lock()
        self._ozon_lock = asyncio.Lock()

    async def prewarm(self) -> None:
        await asyncio.gather(self._ensure_wb(), self._ensure_ozon())

    async def parse_wildberries(
        self,
        keyword: str,
        limit: int,
        *,
        skip: int = 0,
        dest: int = -1257786,
    ) -> list[dict]:
        parser = await self._ensure_wb()
        return await parser.run(keyword, limit, skip=skip, dest=dest)

    async def parse_ozon(self, query: str, limit: int) -> list[dict]:
        from src.api.parsers.search_ozon import parse_ozon_with_parser

        parser = await self._ensure_ozon()
        return await parse_ozon_with_parser(parser, query, limit)

    async def shutdown(self) -> None:
        async with self._wb_lock:
            if self._wb:
                await self._wb.close()
                self._wb = None
        async with self._ozon_lock:
            if self._ozon:
                await self._ozon.close()
                self._ozon = None
        logger.info("Browser session pool stopped")

    async def _ensure_wb(self) -> WildberriesSeleniumParser:
        async with self._wb_lock:
            if self._wb is None:
                parser = WildberriesSeleniumParser(
                    headless=wildberries_settings.headless,
                    page_load_timeout=wildberries_settings.page_load_timeout,
                    element_wait_timeout=wildberries_settings.element_wait_timeout,
                    page_load_retries=wildberries_settings.page_load_retries,
                    keep_alive=True,
                )
                await parser.start()
                self._wb = parser
                logger.info("Wildberries browser session ready")
            return self._wb

    async def _ensure_ozon(self) -> OzonSeleniumParser:
        async with self._ozon_lock:
            if self._ozon is None:
                cookies_path = ozon_settings.resolve_cookies_path(settings_dir=settings_dir)
                parser = OzonSeleniumParser(
                    headless=ozon_settings.headless,
                    slow_mode=ozon_settings.slow,
                    cookies_file=cookies_path,
                    proxy=ozon_settings.resolve_proxy(),
                    page_load_timeout=ozon_settings.page_load_timeout,
                    element_wait_timeout=ozon_settings.element_wait_timeout,
                    page_load_retries=ozon_settings.page_load_retries,
                    keep_alive=True,
                    session_ready=bool(cookies_path),
                )
                await parser.start()
                self._ozon = parser
                logger.info("Ozon browser session ready")
            return self._ozon


_pool: BrowserSessionPool | None = None


def init_browser_session_pool() -> BrowserSessionPool:
    global _pool  # noqa: PLW0603
    _pool = BrowserSessionPool()
    logger.info("Browser session pool created")
    return _pool


def get_browser_session_pool() -> BrowserSessionPool:
    if _pool is None:
        raise RuntimeError("Browser session pool is not initialized. Check application lifespan.")
    return _pool

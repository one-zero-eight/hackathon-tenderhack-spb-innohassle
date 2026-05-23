from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from src.api.parsers.ozon.parser import OzonParser
from src.api.parsers.ozon.run import run_ozon_search
from src.api.parsers.wildberries.parser import WildberriesSeleniumParser
from src.config import browser_pool_settings, ozon_settings, settings_dir, wildberries_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class _ParserSlotPool[T]:
    """N independent browser sessions; one free slot per request."""

    def __init__(self, *, name: str, size: int, create: Callable[[], Awaitable[T]]) -> None:
        self._name = name
        self._size = max(1, min(size, 5))
        self._create = create
        self._parsers: list[T] = []
        self._available: asyncio.Queue[int] = asyncio.Queue()
        self._init_lock = asyncio.Lock()
        self._initialized = False

    @property
    def size(self) -> int:
        return self._size

    async def ensure_ready(self) -> None:
        if self._initialized:
            return
        async with self._init_lock:
            if self._initialized:
                return
            for index in range(self._size):
                parser = await self._create()
                self._parsers.append(parser)
                self._available.put_nowait(index)
                logger.info("%s slot %d/%d ready", self._name, index + 1, self._size)
            self._initialized = True

    async def run(self, fn: Callable[[T], Awaitable[object]]) -> object:
        await self.ensure_ready()
        slot_index = await self._available.get()
        try:
            return await fn(self._parsers[slot_index])
        finally:
            self._available.put_nowait(slot_index)

    async def shutdown(self) -> None:
        for index, parser in enumerate(self._parsers):
            close = getattr(parser, "close", None)
            if close:
                try:
                    await close(force=True)
                except Exception as exc:
                    logger.warning("%s slot %d close failed: %s", self._name, index, exc)
            driver = getattr(parser, "driver", None)
            if driver:
                try:
                    await driver.quit()
                except Exception as exc:
                    logger.warning("%s slot %d driver quit failed: %s", self._name, index, exc)
        self._parsers.clear()
        while not self._available.empty():
            self._available.get_nowait()
        self._initialized = False


class BrowserSessionPool:
    """Browser pool: Wildberries (selenium-driverless) + Ozon (CloakBrowser)."""

    def __init__(self) -> None:
        self._wb = _ParserSlotPool(
            name="Wildberries",
            size=browser_pool_settings.wildberries_pool_size,
            create=self._create_wb_parser,
        )
        self._ozon = _ParserSlotPool(
            name="Ozon",
            size=browser_pool_settings.ozon_pool_size,
            create=self._create_ozon_parser,
        )

    @property
    def wildberries_pool_size(self) -> int:
        return self._wb.size

    @property
    def ozon_pool_size(self) -> int:
        return self._ozon.size

    async def prewarm(self) -> None:
        await asyncio.gather(self._wb.ensure_ready(), self._ozon.ensure_ready())

        async def warmup_wb(parser: WildberriesSeleniumParser) -> None:
            try:
                await parser.warmup_session()
            except Exception as exc:
                logger.warning("WB slot warmup failed: %s", exc)

        for slot in range(1, self._wb.size + 1):
            logger.info("WB warmup slot %d/%d", slot, self._wb.size)
            await self._wb.run(warmup_wb)  # type: ignore[arg-type]
            if slot < self._wb.size:
                await asyncio.sleep(1.5)

        async def warmup_ozon(parser: OzonSeleniumParser) -> None:
            try:
                await parser.warmup_session()
            except Exception as exc:
                logger.warning("Ozon slot warmup failed: %s", exc)

        for slot in range(1, self._ozon.size + 1):
            logger.info("Ozon warmup slot %d/%d", slot, self._ozon.size)
            await self._ozon.run(warmup_ozon)  # type: ignore[arg-type]

        logger.info(
            "Browser pool prewarmed (WB slots=%d, Ozon CloakBrowser slots=%d)",
            self._wb.size,
            self._ozon.size,
        )

    async def parse_wildberries(
        self,
        keyword: str,
        limit: int,
        *,
        skip: int = 0,
        dest: int = -1257786,
    ) -> list[dict]:
        result = await self._wb.run(
            lambda parser: parser.run(keyword, limit, skip=skip, dest=dest),
        )
        return result  # type: ignore[return-value]

    async def parse_ozon(self, query: str, limit: int) -> list[dict]:
        result = await self._ozon.run(
            lambda parser: run_ozon_search(parser, query, limit),
        )
        return result  # type: ignore[return-value]

    async def shutdown(self) -> None:
        await asyncio.gather(self._wb.shutdown(), self._ozon.shutdown())
        logger.info("Browser session pool stopped")

    async def _create_wb_parser(self) -> WildberriesSeleniumParser:
        parser = WildberriesSeleniumParser(
            headless=wildberries_settings.headless,
            page_load_timeout=wildberries_settings.page_load_timeout,
            element_wait_timeout=wildberries_settings.element_wait_timeout,
            page_load_retries=wildberries_settings.page_load_retries,
            keep_alive=True,
        )
        await parser.start()
        return parser

    async def _create_ozon_parser(self) -> OzonParser:
        cookies_path = ozon_settings.resolve_cookies_path(settings_dir=settings_dir)
        parser = OzonParser(
            headless=ozon_settings.headless,
            slow_mode=ozon_settings.slow,
            cookies_file=cookies_path,
            proxy=ozon_settings.resolve_proxy(),
            geoip=bool(ozon_settings.resolve_proxy()),
            page_load_timeout=ozon_settings.page_load_timeout,
            element_wait_timeout=ozon_settings.element_wait_timeout,
            page_load_retries=ozon_settings.page_load_retries,
            keep_alive=True,
        )
        await parser.start()
        return parser


_pool: BrowserSessionPool | None = None


def init_browser_session_pool() -> BrowserSessionPool:
    global _pool  # noqa: PLW0603
    _pool = BrowserSessionPool()
    logger.info(
        "Browser session pool created (WB=%d, Ozon=%d)",
        _pool.wildberries_pool_size,
        _pool.ozon_pool_size,
    )
    return _pool


def get_browser_session_pool() -> BrowserSessionPool:
    if _pool is None:
        raise RuntimeError("Browser session pool is not initialized. Check application lifespan.")
    return _pool

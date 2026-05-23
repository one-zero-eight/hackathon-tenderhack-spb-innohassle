import logging

from src.api.parsers.browser_session_pool import get_browser_session_pool
from src.api.parsers.ozon.exceptions import OzonAccessError
from src.api.parsers.ozon.parser import OzonSeleniumParser
from src.api.parsers.ozon.run import run_ozon_search
from src.config import ozon_settings, settings_dir

logger = logging.getLogger(__name__)


async def parse_ozon_products(query: str, limit: int = 5) -> list[dict]:
    """Parse Ozon via pooled Chrome session (warm browser, ~5s per request)."""
    try:
        return await get_browser_session_pool().parse_ozon(query, limit)
    except (OzonAccessError, ValueError, RuntimeError) as exc:
        logger.error("Ozon parse failed for %r: %s", query, exc)
        raise


async def parse_ozon_products_cold(query: str, limit: int = 5) -> list[dict]:
    """Разовый парсинг с закрытием Chrome (fallback без пула)."""
    cookies_path = ozon_settings.resolve_cookies_path(settings_dir=settings_dir)
    async with OzonSeleniumParser(
        headless=ozon_settings.headless,
        slow_mode=ozon_settings.slow,
        cookies_file=cookies_path,
        proxy=ozon_settings.resolve_proxy(),
        page_load_timeout=ozon_settings.page_load_timeout,
        element_wait_timeout=ozon_settings.element_wait_timeout,
        page_load_retries=ozon_settings.page_load_retries,
    ) as parser:
        return await run_ozon_search(parser, query, limit)

import logging

from src.api.parsers.browser_session_pool import get_browser_session_pool
from src.api.parsers.ozon.exceptions import OzonAccessError
from src.api.parsers.ozon.parser import OzonParser
from src.api.parsers.ozon.run import run_ozon_search
from src.config import ozon_settings, settings_dir

logger = logging.getLogger(__name__)


async def parse_ozon_products(
    query: str,
    limit: int = 5,
    skip: int = 0,
    *,
    location: str | None = None,
) -> list[dict]:
    """Parse Ozon via pooled CloakBrowser sessions."""
    try:
        return await get_browser_session_pool().parse_ozon(
            query,
            limit,
            skip=skip,
            location=location,
        )
    except (OzonAccessError, ValueError, RuntimeError) as exc:
        logger.error("Ozon parse failed for %r: %s", query, exc)
        raise


async def parse_ozon_products_cold(
    query: str,
    limit: int = 5,
    skip: int = 0,
    *,
    location: str | None = None,
) -> list[dict]:
    """One-off parse with a fresh CloakBrowser session (no pool)."""
    cookies_path = ozon_settings.resolve_cookies_path(settings_dir=settings_dir)
    async with OzonParser(
        headless=ozon_settings.headless,
        slow_mode=ozon_settings.slow,
        cookies_file=cookies_path,
        proxy=ozon_settings.resolve_proxy(),
        geoip=bool(ozon_settings.resolve_proxy()),
        page_load_timeout=ozon_settings.page_load_timeout,
        element_wait_timeout=ozon_settings.element_wait_timeout,
        page_load_retries=ozon_settings.page_load_retries,
    ) as parser:
        return await run_ozon_search(parser, query, limit, skip=skip, location=location)

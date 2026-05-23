import logging

from src.api.parsers.geocoder import resolve_wb_dest
from src.api.parsers.wildberries.exceptions import WildberriesAccessError
from src.api.parsers.wildberries.parser import WildberriesSeleniumParser
from src.config import api_settings, wildberries_settings

logger = logging.getLogger(__name__)


async def parse_wildberries_products(
    keyword: str,
    limit: int = 5,
    skip: int = 0,
    location: str | None = None,
) -> list[dict]:
    """Parse Wildberries search results via selenium-driverless.

    Args:
        keyword: Search query.
        limit: Maximum number of results.
        skip: Number of results to skip.
        location: City/region for regional pricing (e.g. 'Санкт-Петербург').
                  Defaults to Moscow when omitted.
    """
    dest = resolve_wb_dest(location, api_settings.nominatim_url)
    logger.info(
        "Wildberries parse start: keyword=%r limit=%d skip=%d dest=%d location=%r headless=%s",
        keyword,
        limit,
        skip,
        dest,
        location,
        wildberries_settings.headless,
    )

    try:
        async with WildberriesSeleniumParser(
            headless=wildberries_settings.headless,
            page_load_timeout=wildberries_settings.page_load_timeout,
            element_wait_timeout=wildberries_settings.element_wait_timeout,
            page_load_retries=wildberries_settings.page_load_retries,
        ) as parser:
            return await parser.run(keyword, limit, skip=skip, dest=dest)
    except WildberriesAccessError as exc:
        logger.error("Wildberries parse failed for %r: %s", keyword, exc)
        raise RuntimeError(f"Failed to scrape Wildberries: {exc}") from exc

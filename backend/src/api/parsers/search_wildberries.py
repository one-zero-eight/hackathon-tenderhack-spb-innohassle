import logging

from src.api.parsers.browser_session_pool import get_browser_session_pool
from src.api.parsers.geocoder import resolve_wb_dest
from src.api.parsers.wildberries.exceptions import WildberriesAccessError

logger = logging.getLogger(__name__)


async def parse_wildberries_products(
    keyword: str,
    limit: int = 5,
    skip: int = 0,
    location: str | None = None,
) -> list[dict]:
    """Parse Wildberries via pooled Chrome sessions (warm browser, regional pricing)."""
    dest = resolve_wb_dest(location)
    logger.info(
        "Wildberries parse start: keyword=%r limit=%d skip=%d dest=%d location=%r (pooled)",
        keyword,
        limit,
        skip,
        dest,
        location,
    )
    try:
        return await get_browser_session_pool().parse_wildberries(
            keyword,
            limit,
            skip=skip,
            dest=dest,
        )
    except WildberriesAccessError as exc:
        logger.error("Wildberries parse failed for %r: %s", keyword, exc)
        raise RuntimeError(f"Failed to scrape Wildberries: {exc}") from exc
    except RuntimeError as exc:
        logger.error("Wildberries parse failed for %r: %s", keyword, exc)
        raise RuntimeError(f"Failed to scrape Wildberries: {exc}") from exc

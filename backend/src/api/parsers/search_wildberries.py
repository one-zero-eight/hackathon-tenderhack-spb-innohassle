import logging

from src.api.parsers.browser_session_pool import get_browser_session_pool
from src.api.parsers.wildberries.exceptions import WildberriesAccessError

logger = logging.getLogger(__name__)

# Moscow delivery region (search.wb.ru ``dest`` parameter).
WB_MOSCOW_DEST = -1257786


async def parse_wildberries_products(
    keyword: str,
    limit: int = 5,
    skip: int = 0,
    *,
    dest: int = WB_MOSCOW_DEST,
) -> list[dict]:
<<<<<<< HEAD
    """Parse Wildberries via pooled Chrome sessions (warm browser)."""
=======
    """Parse Wildberries via pooled Chrome sessions (warm browser, regional pricing)."""
    dest = resolve_wb_dest(location)
>>>>>>> 5be78a8 (feat: remove nominatim as it turned way too much time to load. Translate all logs to English)
    logger.info(
        "Wildberries parse start: keyword=%r limit=%d skip=%d dest=%d (pooled)",
        keyword,
        limit,
        skip,
        dest,
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

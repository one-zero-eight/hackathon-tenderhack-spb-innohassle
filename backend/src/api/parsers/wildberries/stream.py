from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from src.api.parsers.geocoder import resolve_wb_dest
from src.api.parsers.wildberries.parser import WildberriesParser

logger = logging.getLogger(__name__)


async def iter_wildberries_search_api_raw(
    parser: WildberriesParser,
    keyword: str,
    limit: int,
    *,
    skip: int = 0,
    location: str | None = None,
) -> AsyncIterator[dict]:
    """Deprecated alias: streams product batches parsed from CloakBrowser DOM."""
    dest = resolve_wb_dest(location)
    logger.info(
        "WB stream (DOM): keyword=%r limit=%d skip=%d dest=%d",
        keyword,
        limit,
        skip,
        dest,
    )
    async for batch in parser.iter_products(keyword, limit, skip=skip, dest=dest, batch_size=limit):
        yield {
            "page": 1,
            "ok": True,
            "status": 200,
            "search_url": None,
            "products": batch,
        }

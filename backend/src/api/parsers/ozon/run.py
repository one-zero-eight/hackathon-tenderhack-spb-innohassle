import logging
import re

from src.api.parsers.ozon.exceptions import OzonAccessError
from src.api.parsers.ozon.parser import OzonParser
from src.config import ozon_settings

logger = logging.getLogger(__name__)


async def run_ozon_search(parser: OzonParser, query: str, limit: int) -> list[dict]:
    fetch_details = ozon_settings.fetch_details
    batch_size = max(1, (limit - 1) // 2) if limit > 1 else 1

    logger.info(
        "Ozon parse start: query=%r limit=%d fetch_details=%s",
        query,
        limit,
        fetch_details,
    )

    try:
        raw_results = await parser.run(
            query,
            limit,
            fetch_details=fetch_details,
            batch_size=batch_size,
        )
    except (OzonAccessError, ValueError):
        raise

    results = []
    for product in raw_results[:limit]:
        sale_price = _parse_price(product.price) or _parse_price(product.title)
        results.append(
            {
                "name": product.title,
                "sale_price": sale_price,
                "url": product.url,
                "image_url": product.image_url,
                "source": "Ozon",
            }
        )

    logger.info(
        "Ozon parse done for %r (limit=%d): %d items, %d with price",
        query,
        limit,
        len(results),
        sum(1 for item in results if item.get("sale_price") is not None),
    )
    return results


def _parse_price(price: str | None) -> float | None:
    if not price:
        return None
    digits = re.sub(r"[^\d]", "", price.replace("\u00a0", " ").replace(" ", ""))
    if not digits:
        return None
    value = float(digits)
    return value if value > 0 else None

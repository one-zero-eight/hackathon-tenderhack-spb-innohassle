import logging
import re

from src.api.parsers.browser_session_pool import get_browser_session_pool
from src.api.parsers.ozon.exceptions import OzonAccessError
from src.api.parsers.ozon.parser import OzonSeleniumParser
from src.config import ozon_settings, settings_dir

logger = logging.getLogger(__name__)


async def parse_ozon_products(query: str, limit: int = 5) -> list[dict]:
    """Parse Ozon via pooled Chrome session (warm browser, ~5s per request)."""
    try:
        return await get_browser_session_pool().parse_ozon(query, limit)
    except (OzonAccessError, ValueError, RuntimeError) as exc:
        logger.error("Ozon parse failed for %r: %s", query, exc)
        raise


async def parse_ozon_with_parser(parser: OzonSeleniumParser, query: str, limit: int) -> list[dict]:
    fetch_details = ozon_settings.fetch_details
    parser_limit = limit
    batch_size = max(1, (parser_limit - 1) // 2) if parser_limit > 1 else 1

    logger.info(
        "Ozon parse start: query=%r limit=%d parser_limit=%d fetch_details=%s (pooled)",
        query,
        limit,
        parser_limit,
        fetch_details,
    )

    raw_results = await parser.run(
        query,
        parser_limit,
        fetch_details=fetch_details,
        batch_size=batch_size,
    )

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
        return await parse_ozon_with_parser(parser, query, limit)


def _parse_price(price: str | None) -> float | None:
    if not price:
        return None
    digits = re.sub(r"[^\d]", "", price.replace("\u00a0", " ").replace(" ", ""))
    if not digits:
        return None
    value = float(digits)
    return value if value > 0 else None

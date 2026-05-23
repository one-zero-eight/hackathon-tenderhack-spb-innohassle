import logging
import re

from src.api.parsers.ozon.exceptions import OzonAccessError
from src.api.parsers.ozon.parser import OzonSeleniumParser
from src.config import ozon_settings, settings_dir

logger = logging.getLogger(__name__)


async def parse_ozon_products(query: str, limit: int = 5) -> list[dict]:
    """Parse Ozon search results asynchronously via selenium-driverless."""
    headless = ozon_settings.headless
    slow_mode = ozon_settings.slow
    proxy = ozon_settings.resolve_proxy()
    fetch_details = ozon_settings.fetch_details

    cookies_path = ozon_settings.resolve_cookies_path(settings_dir=settings_dir)

    parser_limit = max(limit, 3)
    batch_size = max(1, (parser_limit - 1) // 2)

    logger.info(
        "Ozon parse start: query=%r limit=%d parser_limit=%d headless=%s slow=%s proxy=%s fetch_details=%s",
        query,
        limit,
        parser_limit,
        headless,
        slow_mode,
        bool(proxy),
        fetch_details,
    )

    try:
        async with OzonSeleniumParser(
            headless=headless,
            slow_mode=slow_mode,
            cookies_file=cookies_path,
            proxy=proxy,
            page_load_timeout=ozon_settings.page_load_timeout,
            element_wait_timeout=ozon_settings.element_wait_timeout,
            page_load_retries=ozon_settings.page_load_retries,
        ) as parser:
            raw_results = await parser.run(
                query,
                parser_limit,
                fetch_details=fetch_details,
                batch_size=batch_size,
            )
    except (OzonAccessError, ValueError) as exc:
        logger.error("Ozon parse failed for %r: %s", query, exc)
        raise

    logger.info(
        "Ozon raw products: %d, with price string: %d",
        len(raw_results),
        sum(1 for p in raw_results if p.price),
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


def _parse_price(price: str | None) -> float | None:
    if not price:
        return None
    digits = re.sub(r"[^\d]", "", price.replace("\u00a0", " ").replace(" ", ""))
    if not digits:
        return None
    value = float(digits)
    return value if value > 0 else None

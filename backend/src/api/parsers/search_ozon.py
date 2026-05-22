import asyncio
import os
import re
from pathlib import Path

from src.api.parsers.ozon.parser import OzonSeleniumParser
from src.config import ozon_settings

DEFAULT_COOKIES_PATH = Path(__file__).resolve().parents[3] / "cookies.json"


async def parse_ozon_products(query: str, limit: int = 5) -> list[dict]:
    """Parse Ozon search results asynchronously."""
    return await asyncio.to_thread(_parse_ozon_products_sync, query, limit)


def _parse_ozon_products_sync(query: str, limit: int = 5) -> list[dict]:
    headless = ozon_settings.headless
    slow_mode = ozon_settings.slow
    proxy = ozon_settings.resolve_proxy()

    cookies_path: Path | None = None
    cookies_env = os.environ.get("OZON_COOKIES_FILE")
    if cookies_env:
        cookies_path = Path(cookies_env)
    elif DEFAULT_COOKIES_PATH.is_file():
        cookies_path = DEFAULT_COOKIES_PATH

    parser_limit = max(limit, 3)
    batch_size = max(1, (parser_limit - 1) // 2)

    with OzonSeleniumParser(
        headless=headless,
        slow_mode=slow_mode,
        cookies_file=cookies_path,
        proxy=proxy,
        page_load_timeout=ozon_settings.page_load_timeout,
        element_wait_timeout=ozon_settings.element_wait_timeout,
        page_load_retries=ozon_settings.page_load_retries,
    ) as parser:
        results = parser.run(
            query,
            parser_limit,
            fetch_details=False,
            batch_size=batch_size,
        )

    return [
        {
            "name": product.title,
            "sale_price": _parse_price(product.price),
            "url": product.url,
            "image_url": product.image_url,
            "source": "Ozon",
        }
        for product in results[:limit]
        if _parse_price(product.price) is not None
    ]


def _parse_price(price: str | None) -> float | None:
    if not price:
        return None
    digits = re.sub(r"[^\d]", "", price.replace("\u00a0", " ").replace(" ", ""))
    if not digits:
        return None
    return float(digits)

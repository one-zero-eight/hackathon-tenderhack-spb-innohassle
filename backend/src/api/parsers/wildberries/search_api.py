"""Legacy search.wb.ru JSON helpers (DOM parsing is default; see dom_extract.py)."""

from __future__ import annotations

from typing import Any

# Kept for optional JSON-based tooling / search_products.collect_products_from_search_pages.


def products_from_api_payload(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    products = payload.get("products")
    if not isinstance(products, list):
        data = payload.get("data")
        if isinstance(data, dict):
            products = data.get("products")
    if not isinstance(products, list):
        return []
    return [item for item in products if isinstance(item, dict)]


def rub_from_api_units(value: object) -> float | None:
    if value is None:
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    return amount / 100.0


def _price_pair_from_size_price(price: object) -> tuple[float | None, float | None]:
    if isinstance(price, dict):
        sale = rub_from_api_units(price.get("product") or price.get("total"))
        original = rub_from_api_units(price.get("basic"))
        if original is not None and sale is not None and abs(original - sale) < 0.01:
            original = None
        return sale, original
    return rub_from_api_units(price), None


def extract_item_prices(item: dict[str, Any]) -> tuple[float | None, float | None]:
    for key in ("salePriceU", "salePrice", "sale", "priceU"):
        sale = rub_from_api_units(item.get(key))
        if sale is not None:
            original = rub_from_api_units(item.get("priceU"))
            if original is not None and abs(original - sale) < 0.01:
                original = None
            return sale, original

    best_sale: float | None = None
    best_original: float | None = None
    sizes = item.get("sizes")
    if isinstance(sizes, list):
        for size in sizes:
            if not isinstance(size, dict):
                continue
            sale, original = _price_pair_from_size_price(size.get("price"))
            if sale is None:
                sale = rub_from_api_units(size.get("salePrice"))
            if sale is None:
                continue
            if best_sale is None or sale < best_sale:
                best_sale = sale
                best_original = original
    return best_sale, best_original


def wb_image_url(nm_id: int) -> str | None:
    if nm_id <= 0:
        return None
    vol = nm_id // 100000
    part = nm_id // 1000
    basket = f"{(vol % 10) + 1:02d}"
    return f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/images/c516x688/1.webp"


def api_item_to_product(item: dict[str, Any]) -> dict[str, Any] | None:
    nm = item.get("id")
    if nm is None:
        return None
    try:
        nm_id = int(nm)
    except (TypeError, ValueError):
        return None

    sale_price, original_price = extract_item_prices(item)
    if sale_price is None:
        return None

    brand = item.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")

    return {
        "name": item.get("name"),
        "brand": str(brand).strip() if brand else None,
        "sale_price": sale_price,
        "original_price": original_price,
        "url": f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx",
        "image_url": wb_image_url(nm_id),
        "source": "Wildberries",
    }

"""Parse Ozon search/product data from composer-api widgetStates."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse

from src.api.parsers.ozon.titles import is_valid_ozon_product_title

logger = logging.getLogger(__name__)

OZON_HOME = "https://www.ozon.ru/"
COMPOSER_API_ENDPOINT = f"{OZON_HOME}api/composer-api.bx/page/json/v2"

COMPOSER_HTTP_HEADERS = {
    "accept": "application/json",
    "x-o3-app-name": "dweb_search",
}


def composer_api_url(path: str) -> str:
    return f"{COMPOSER_API_ENDPOINT}?url={quote(path, safe='')}"


def composer_path_strip_page(path: str) -> str:
    if "?" not in path:
        return path
    pathname, query = path.split("?", 1)
    pairs = [(key, value) for key, value in parse_qsl(query, keep_blank_values=True) if key != "page"]
    return pathname + (f"?{urlencode(pairs)}" if pairs else "")


def composer_path_with_page(path: str, page: int) -> str:
    if page <= 1:
        return path
    base = composer_path_strip_page(path)
    sep = "&" if "?" in base else "?"
    if "page=" in base:
        return base
    return f"{base}{sep}page={page}"


FETCH_COMPOSER_JS = """
async (explicitPath) => {
  const path = explicitPath || (window.location.pathname + window.location.search);
  try {
    const r = await fetch(
      '/api/composer-api.bx/page/json/v2?url=' + encodeURIComponent(path),
      {
        credentials: 'include',
        headers: {
          accept: 'application/json',
          'x-o3-app-name': 'dweb_search',
        },
        referrer: window.location.href,
      }
    );
    if (!r.ok) return { __error: r.status };
    return await r.json();
  } catch (e) {
    return { __error: String(e) };
  }
}
"""


def composer_listing_rows(payload: object, *, limit: int) -> list[dict[str, Any]]:
    """Ordered listing rows from a composer-api search payload."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in parse_composer_search(payload):
        url = normalize_product_url(str(item.get("url") or ""))
        if not url or url in seen:
            continue
        seen.add(url)
        rows.append(
            {
                "url": url,
                "title": item.get("title") or "Без названия",
                "price": item.get("price"),
                "originalPrice": item.get("originalPrice"),
                "image": item.get("image"),
            }
        )
        if len(rows) >= limit:
            break
    return rows


def normalize_product_url(href: str) -> str | None:
    if "/product/" not in href:
        return None
    full = urljoin(OZON_HOME, href)
    parsed = urlparse(full)
    if "ozon.ru" not in parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def parse_composer_search(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    if payload.get("__error") is not None:
        logger.warning("Ozon composer-api error: %s", payload.get("__error"))
        return []

    widgets = payload.get("widgetStates")
    if not isinstance(widgets, dict):
        return []

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key, raw in widgets.items():
        state: object = raw
        if isinstance(raw, str):
            try:
                state = json.loads(raw)
            except json.JSONDecodeError:
                continue
        if isinstance(key, str) and key.startswith("tileGridDesktop") and isinstance(state, dict):
            _parse_tile_grid_state(state, out, seen)
    if not out:
        for raw in widgets.values():
            state: object = raw
            if isinstance(raw, str):
                try:
                    state = json.loads(raw)
                except json.JSONDecodeError:
                    continue
            _walk_widget(state, out, seen)
    return out


def _parse_tile_grid_state(state: dict[str, Any], out: list[dict[str, Any]], seen: set[str]) -> None:
    items = state.get("items")
    if not isinstance(items, list):
        tiles = state.get("tiles")
        items = tiles if isinstance(tiles, list) else []
    for tile in items:
        if not isinstance(tile, dict):
            continue
        _maybe_append_tile(tile, out, seen)


def _maybe_append_tile(tile: dict[str, Any], out: list[dict[str, Any]], seen: set[str]) -> None:
    url = _pick_url(tile)
    if not url or url in seen:
        return
    main = tile.get("mainState")
    sale_price, original_price = _pick_prices_from_main_state(main)
    title = _pick_title_from_main_state(main) or _pick_title(tile)
    if not title and not sale_price:
        return
    seen.add(url)
    out.append(
        {
            "url": url,
            "title": title or "Без названия",
            "price": sale_price,
            "originalPrice": original_price,
            "image": _pick_image(tile) or _pick_tile_image(tile),
        }
    )


def _image_url_from_value(value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        if not text or text.startswith("data:"):
            return None
        if text.startswith("//"):
            return f"https:{text}"
        if text.startswith("http"):
            return text
        return None
    if isinstance(value, dict):
        for key in ("link", "url", "src", "image", "imageUrl"):
            found = _image_url_from_value(value.get(key))
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _image_url_from_value(item)
            if found:
                return found
    return None


def _pick_tile_image(tile: dict[str, Any]) -> str | None:
    tile_image = tile.get("tileImage")
    if not isinstance(tile_image, dict):
        return None
    for key in ("image", "link", "url"):
        found = _image_url_from_value(tile_image.get(key))
        if found:
            return found
    items = tile_image.get("items")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                found = _image_url_from_value(item.get("image")) or _image_url_from_value(item)
                if found:
                    return found
    return None


def _pick_prices_from_main_state(main: object) -> tuple[str | None, str | None]:
    if not isinstance(main, list):
        return None, None
    sale: str | None = None
    original: str | None = None
    for block in main:
        if not isinstance(block, dict) or block.get("type") != "priceV2":
            continue
        price_v2 = block.get("priceV2")
        if not isinstance(price_v2, dict):
            continue
        entries = price_v2.get("price")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            text = entry.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            style = str(entry.get("textStyle") or "").upper()
            if style == "ORIGINAL_PRICE":
                original = text.strip()
            elif sale is None:
                sale = text.strip()
    return sale, original


def _pick_title_from_main_state(main: object) -> str | None:
    if not isinstance(main, list):
        return None
    candidates: list[str] = []
    for block in main:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "textAtom":
            text_atom = block.get("textAtom")
            if isinstance(text_atom, dict):
                text = text_atom.get("text")
                if isinstance(text, str):
                    candidates.append(text.strip()[:500])
        atom = block.get("atom")
        if isinstance(atom, dict):
            text = atom.get("text")
            if isinstance(text, str):
                candidates.append(text.strip()[:500])
    for text in candidates:
        if is_valid_ozon_product_title(text):
            return text
    return candidates[0] if candidates else None


def composer_items_by_url(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_url: dict[str, dict[str, Any]] = {}
    for item in items:
        url = normalize_product_url(str(item.get("url") or item.get("href") or ""))
        if url:
            by_url[url] = item
    return by_url


def _walk_widget(obj: object, out: list[dict[str, Any]], seen: set[str]) -> None:
    if isinstance(obj, dict):
        _maybe_append_product(obj, out, seen)
        for value in obj.values():
            _walk_widget(value, out, seen)
    elif isinstance(obj, list):
        for item in obj:
            _walk_widget(item, out, seen)


def _maybe_append_product(obj: dict[str, Any], out: list[dict[str, Any]], seen: set[str]) -> None:
    url = _pick_url(obj)
    if not url:
        return
    title = _pick_title(obj)
    price = _pick_price_text(obj)
    if not title and not price:
        return
    if url in seen:
        return
    seen.add(url)
    out.append(
        {
            "url": url,
            "title": title or "Без названия",
            "price": price,
            "originalPrice": _pick_original_price_text(obj),
            "image": _pick_image(obj) or _pick_tile_image(obj),
        }
    )


def _pick_url(obj: dict[str, Any]) -> str | None:
    for key in ("link", "href", "url", "webUrl", "productUrl"):
        value = obj.get(key)
        if isinstance(value, str):
            normalized = normalize_product_url(value)
            if normalized:
                return normalized
    action = obj.get("action")
    if isinstance(action, dict):
        link = action.get("link") or action.get("href")
        if isinstance(link, str):
            return normalize_product_url(link)
    tracking = obj.get("cellTrackingInfo")
    if isinstance(tracking, dict):
        product = tracking.get("product")
        if isinstance(product, dict):
            link = product.get("link") or product.get("url")
            if isinstance(link, str):
                return normalize_product_url(link)
    return None


def _pick_title(obj: dict[str, Any]) -> str | None:
    candidates: list[str] = []
    for key in ("title", "name", "text", "productName"):
        value = obj.get(key)
        if isinstance(value, str) and is_valid_ozon_product_title(value):
            candidates.append(value.strip()[:500])
    tracking = obj.get("cellTrackingInfo")
    if isinstance(tracking, dict):
        product = tracking.get("product")
        if isinstance(product, dict):
            title = product.get("title")
            if isinstance(title, str) and is_valid_ozon_product_title(title):
                candidates.append(title.strip()[:500])
    main = obj.get("mainState")
    title_from_main = _pick_title_from_main_state(main)
    if title_from_main:
        candidates.append(title_from_main)
    if isinstance(main, list):
        for block in main:
            if not isinstance(block, dict):
                continue
            atom = block.get("atom")
            if isinstance(atom, dict):
                text = atom.get("text")
                if isinstance(text, str) and is_valid_ozon_product_title(text):
                    candidates.append(text.strip()[:500])
    if not candidates:
        return None
    return max(candidates, key=len)


def _pick_price_text(obj: dict[str, Any]) -> str | None:
    for key in ("finalPrice", "price", "cardPrice", "marketingPrice"):
        text = _price_value_to_text(obj.get(key))
        if text:
            return text
    tracking = obj.get("cellTrackingInfo")
    if isinstance(tracking, dict):
        product = tracking.get("product")
        if isinstance(product, dict):
            for key in ("finalPrice", "price"):
                text = _price_value_to_text(product.get(key))
                if text:
                    return text
    main = obj.get("mainState")
    sale, _ = _pick_prices_from_main_state(main)
    if sale:
        return sale
    if isinstance(main, list):
        for block in main:
            if not isinstance(block, dict):
                continue
            price_block = block.get("priceV2") or block.get("price")
            if isinstance(price_block, dict):
                text = _price_value_to_text(price_block.get("price") or price_block.get("finalPrice"))
                if text:
                    return text
    return None


def _pick_original_price_text(obj: dict[str, Any]) -> str | None:
    for key in ("originalPrice", "oldPrice", "basePrice"):
        text = _price_value_to_text(obj.get(key))
        if text:
            return text
    tracking = obj.get("cellTrackingInfo")
    if isinstance(tracking, dict):
        product = tracking.get("product")
        if isinstance(product, dict):
            text = _price_value_to_text(product.get("originalPrice"))
            if text:
                return text
    return None


def _pick_image(obj: dict[str, Any]) -> str | None:
    for key in ("image", "imageUrl", "preview", "picture"):
        found = _image_url_from_value(obj.get(key))
        if found:
            return found
    if isinstance(obj.get("images"), list):
        for image in obj["images"]:
            found = _image_url_from_value(image)
            if found:
                return found
    return None


def _price_value_to_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        amount = int(value)
        return f"{amount} ₽" if amount > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            return f"{text} ₽"
        return text if any(ch.isdigit() for ch in text) else None
    if isinstance(value, dict):
        for key in ("price", "value", "text", "finalPrice"):
            nested = _price_value_to_text(value.get(key))
            if nested:
                return nested
    return None

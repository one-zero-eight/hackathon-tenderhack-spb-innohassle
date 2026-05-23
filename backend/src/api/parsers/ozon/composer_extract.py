"""Parse Ozon search/product data from composer-api widgetStates."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

OZON_HOME = "https://www.ozon.ru/"

FETCH_COMPOSER_JS = """
async () => {
  const path = window.location.pathname + window.location.search;
  try {
    const r = await fetch(
      '/api/composer-api.bx/page/json/v2?url=' + encodeURIComponent(path),
      { credentials: 'include', headers: { accept: 'application/json' } }
    );
    if (!r.ok) return { __error: r.status };
    return await r.json();
  } catch (e) {
    return { __error: String(e) };
  }
}
"""


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
    for raw in widgets.values():
        state: object = raw
        if isinstance(raw, str):
            try:
                state = json.loads(raw)
            except json.JSONDecodeError:
                continue
        _walk_widget(state, out, seen)
    return out


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
            "image": _pick_image(obj),
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
    for key in ("title", "name", "text", "productName"):
        value = obj.get(key)
        if isinstance(value, str) and len(value.strip()) > 3:
            return value.strip()[:500]
    tracking = obj.get("cellTrackingInfo")
    if isinstance(tracking, dict):
        product = tracking.get("product")
        if isinstance(product, dict):
            title = product.get("title")
            if isinstance(title, str) and title.strip():
                return title.strip()[:500]
    main = obj.get("mainState")
    if isinstance(main, list):
        for block in main:
            if not isinstance(block, dict):
                continue
            atom = block.get("atom")
            if isinstance(atom, dict):
                text = atom.get("text")
                if isinstance(text, str) and len(text.strip()) > 3 and "₽" not in text:
                    return text.strip()[:500]
    return None


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
        value = obj.get(key)
        if isinstance(value, str) and value.startswith("http"):
            return value
    if isinstance(obj.get("images"), list):
        for image in obj["images"]:
            if isinstance(image, str) and image.startswith("http"):
                return image
            if isinstance(image, dict):
                src = image.get("link") or image.get("url")
                if isinstance(src, str) and src.startswith("http"):
                    return src
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

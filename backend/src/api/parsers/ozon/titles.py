"""Helpers to detect junk titles on Ozon SERP tiles (badges, promos)."""

from __future__ import annotations

import re

_JUNK_TITLES = frozenset({
    "распродажа",
    "скидка",
    "скидки",
    "акция",
    "новинка",
    "хит",
    "хит продаж",
    "бестселлер",
    "выгодно",
    "премиум",
    "premium",
    "оригинал",
    "выбор покупателей",
    "суперцена",
    "цена что надо",
    "завтра",
    "осталось",
})

_PRICE_ONLY_RE = re.compile(r"^[\d\s%₽руб.,+\-–—]+$", re.IGNORECASE)


def is_valid_ozon_product_title(title: str | None) -> bool:
    if not title:
        return False
    text = title.strip()
    if len(text) < 8:
        return False
    if _PRICE_ONLY_RE.match(text):
        return False
    if text.lower() in _JUNK_TITLES:
        return False
    if "₽" in text or "руб" in text.lower():
        return False
    return True


def pick_ozon_product_title(*candidates: str | None) -> str | None:
    valid = [c.strip() for c in candidates if c and is_valid_ozon_product_title(c)]
    if not valid:
        return None
    return max(valid, key=len)

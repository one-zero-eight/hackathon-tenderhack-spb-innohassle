"""Shared helpers to parse RUB prices from marketplace UI strings."""

from __future__ import annotations

import re

_RUBLE_RE = re.compile(
    r"(\d[\d\s\u00a0]*)\s*(?:₽|руб\.?|rub)",
    re.IGNORECASE,
)


def parse_rub_price(value: str | int | float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        amount = float(value)
        return amount if amount > 0 else None
    text = str(value).replace("\u00a0", " ").strip()
    match = _RUBLE_RE.search(text)
    digits_source = match.group(1) if match else text
    digits = re.sub(r"[^\d]", "", digits_source)
    if not digits:
        return None
    amount = float(digits)
    if amount <= 0:
        return None
    # Bare numbers without ₽ are only accepted when they look like real prices.
    if match is None and amount < 10:
        return None
    return amount

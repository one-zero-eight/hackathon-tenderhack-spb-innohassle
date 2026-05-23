"""Коррекция опечаток в поисковых запросах.

Яндекс Спеллер (бренды и незнакомые слова обычно не трогает);
при недоступности — fallback через ``autocorrect``.
"""

from __future__ import annotations

import logging

import httpx
from autocorrect import Speller

SPELLER_URL = "https://speller.yandex.net/services/spellservice.json/checkText"
SPELLER_LANG = "ru,en"
SPELLER_TIMEOUT = 5.0

logger = logging.getLogger(__name__)
_offline_speller: Speller | None = None


def _get_offline_speller() -> Speller:
    global _offline_speller  # noqa: PLW0603
    if _offline_speller is None:
        _offline_speller = Speller("ru", fast=True)
    return _offline_speller


def _apply_speller_corrections(text: str, corrections: list[dict]) -> str:
    for item in sorted(corrections, key=lambda x: -x["pos"]):
        suggestions = item.get("s") or []
        if not suggestions:
            continue
        pos, length = item["pos"], item["len"]
        text = text[:pos] + suggestions[0] + text[pos + length :]
    return text


def spellcheck_yandex(text: str) -> str:
    with httpx.Client(timeout=SPELLER_TIMEOUT) as client:
        response = client.get(
            SPELLER_URL,
            params={"text": text, "lang": SPELLER_LANG},
        )
        response.raise_for_status()
    return _apply_speller_corrections(text, response.json())


def spellcheck_offline(text: str) -> str:
    offline_speller = _get_offline_speller()
    return " ".join(offline_speller(token) for token in text.split())


def spellcheck(text: str) -> str:
    """Исправляет опечатки; при недоступности Яндекс Спеллера — офлайн fallback."""
    text = text.strip()
    if not text:
        return text
    try:
        return spellcheck_yandex(text)
    except (httpx.HTTPError, httpx.TimeoutException):
        try:
            return spellcheck_offline(text)
        except Exception as exc:
            logger.warning("Offline spellcheck failed: %s", exc)
            return text

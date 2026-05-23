"""
LLM-based relevance filter for marketplace search results.

Uses a local Ollama model (granite4.1:8b by default) with structured output
to decide which products actually match the user's query.

Products are sent in small batches so that even compact models can handle
the input without truncation or quality degradation.
"""

from __future__ import annotations

import logging
from typing import Annotated

from ollama import AsyncClient
from pydantic import BaseModel, Field

from src.config import ollama_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Ты — поисковый специалист. Пользователь вводит запрос в поисковую строку \
маркетплейса, маркетплейс предлагает несколько товаров.

Оцени каждый товар: релевантен ли он запросу пользователя.
Товар считается релевантным, если выполнены ВСЕ три условия:
  1. Тип товара совпадает со смыслом запроса (семантическое совпадение).
  2. Производитель (бренд) совпадает — регистр может отличаться.
  3. Модель совпадает точно — учитывай цифры, буквы, индексы.

Если в запросе не указан бренд или модель, оценивай только по совпадающим критериям.
"""


class RelevanceBatch(BaseModel):
    """Structured output: relevance flag for each product in the batch."""

    results: Annotated[
        list[bool],
        Field(description="Relevance flag for each product, in the same order as the input list."),
    ]


async def filter_relevant(query: str, products: list[dict]) -> list[dict]:
    """
    Filter *products* to those relevant to *query* using a local Ollama model.

    If Ollama is unreachable or returns a malformed response the original list
    is returned unchanged so the endpoint never fails silently.

    Args:
        query:    The user's original search query.
        products: Raw product dicts (must have at least a ``name`` key).

    Returns:
        Subset of *products* that the model judged relevant.
    """
    if not products:
        return products

    kept: list[dict] = []
    batch_size = ollama_settings.batch_size

    for offset in range(0, len(products), batch_size):
        batch = products[offset : offset + batch_size]
        flags = await _score_batch(query, batch)
        for product, relevant in zip(batch, flags):
            if relevant:
                kept.append(product)

    logger.info(
        "Relevance filter: %d/%d products kept for query %r",
        len(kept),
        len(products),
        query,
    )
    return kept



async def _score_batch(query: str, batch: list[dict]) -> list[bool]:
    """Ask the LLM to score a single batch. Returns a list of booleans."""
    numbered = "\n".join(
        f"{i + 1}. «{_product_label(p)}»" for i, p in enumerate(batch)
    )
    user_message = (
        f"Запрос пользователя: «{query}»\n\n"
        f"Товары:\n{numbered}"
    )

    try:
        client = AsyncClient(
            host=ollama_settings.host,
            timeout=ollama_settings.timeout,
        )
        response = await client.chat(
            model=ollama_settings.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            format=RelevanceBatch.model_json_schema(),
            options={"temperature": 0},
        )
        result = RelevanceBatch.model_validate_json(response.message.content)
    except Exception as exc:
        logger.warning(
            "Ollama relevance filter failed for batch of %d products (query=%r): %s — skipping filter",
            len(batch),
            query,
            exc,
        )
        return [True] * len(batch)  # pass-through on error

    flags = result.results
    if len(flags) != len(batch):
        logger.warning(
            "Ollama returned %d flags for %d products — passing all through",
            len(flags),
            len(batch),
        )
        return [True] * len(batch)

    return flags


def _product_label(product: dict) -> str:
    """Build a compact display string from a product dict."""
    parts: list[str] = []
    brand = product.get("brand")
    if brand and str(brand).upper() not in ("N/A", "NONE", ""):
        parts.append(brand)
    name = product.get("name") or ""
    if name and name.upper() not in ("N/A", ""):
        parts.append(name)
    return " — ".join(parts) if parts else "(без названия)"

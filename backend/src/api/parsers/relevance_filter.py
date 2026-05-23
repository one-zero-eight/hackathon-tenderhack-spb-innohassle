"""
LLM-based relevance filter for marketplace search results.

Uses a local Ollama model (granite4.1:8b by default) with structured output
to decide which products actually match the user's query.

Products are sent in small batches so that even compact models can handle
the input without truncation or quality degradation.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from ollama import AsyncClient
from pydantic import BaseModel, Field

from src.config import ollama_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Ты — строгий поисковый фильтр для маркетплейсов.
Твоя задача: для каждого товара из списка решить, соответствует ли он запросу пользователя.

ПРАВИЛА (применяй все строго):

1. ТОЧНОЕ совпадение модели.
   Если запрос содержит конкретный номер/индекс модели — все цифры и буквы \
должны совпадать ДОСЛОВНО.
   Примеры отклонения: запрос «Q5» → «Q5 HE», «Q5 Max» — НЕ совпадают (другой суффикс).
   Запрос «Keychron Q5» → «Keychron V5», «Keychron Q1» — НЕ совпадают (другая серия).
   Запрос «Samsung A54» → «Samsung A56», «Samsung A36» — НЕ совпадают (другая цифра).
   Если запрос «Q5 Max», то «Q5 HE» — НЕ совпадает; «Q5 Max» — совпадает.

2. ТОЧНОЕ совпадение бренда.
   Если в запросе указан бренд — бренд товара должен совпадать (регистр игнорируется).
   Пример: запрос «Keychron Q5» → товар бренда INOI или без бренда — НЕ совпадает.

3. ТОЛЬКО сам товар, НЕ аксессуары.
   Отклоняй чехлы, плёнки, стёкла, кабели, подставки и прочие аксессуары,
   даже если они упоминают нужную модель в названии.
   Пример: «Защитное стекло для Samsung A54» — ОТКЛОНИТЬ.
   Пример: «Чехол на Keychron Q5» — ОТКЛОНИТЬ.

4. Если запрос не содержит бренд или модель — оценивай только по типу товара.

Для каждого товара: сначала укажи краткую причину (≤10 слов) в поле reason, затем relevant: true/false.
"""


class RelevanceItem(BaseModel):
    """Verdict for a single product."""

    reason: Annotated[
        str,
        Field(description="One-sentence explanation of the relevance decision."),
    ]
    relevant: Annotated[
        bool,
        Field(description="True if the product matches the query, False otherwise."),
    ]


class RelevanceBatch(BaseModel):
    """Structured output: relevance verdicts for each product in the batch."""

    results: Annotated[
        list[RelevanceItem],
        Field(description="Verdict for each product, in the same order as the input list."),
    ]


async def filter_relevant(query: str, products: list[dict]) -> list[dict]:
    """
    Filter *products* to those relevant to *query* using a local Ollama model.

    Batches are scored **concurrently** (up to ``ollama_settings.concurrency``
    parallel requests) so total latency ≈ slowest single batch, not the sum.

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

    batch_size = ollama_settings.batch_size
    batches = [
        products[offset : offset + batch_size]
        for offset in range(0, len(products), batch_size)
    ]

    # Limit concurrent Ollama requests to avoid overwhelming the server
    semaphore = asyncio.Semaphore(ollama_settings.concurrency)

    async def _score_with_sem(batch: list[dict]) -> list[bool]:
        async with semaphore:
            return await _score_batch(query, batch)

    batch_flags: list[list[bool]] = await asyncio.gather(
        *(_score_with_sem(b) for b in batches)
    )

    kept: list[dict] = []
    for batch, flags in zip(batches, batch_flags):
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
        f"Оцени каждый товар по порядку, верни ровно {len(batch)} результата:\n"
        f"{numbered}"
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

    items = result.results

    # Log reasoning for debugging
    for i, item in enumerate(items):
        logger.debug(
            "[%d] relevant=%s | %s | reason: %s",
            i + 1,
            item.relevant,
            _product_label(batch[i]) if i < len(batch) else "?",
            item.reason,
        )

    if len(items) != len(batch):
        logger.warning(
            "Ollama returned %d items for %d products — truncating/padding",
            len(items),
            len(batch),
        )
        # Truncate if too many, pad with True (pass-through) if too few
        flags = [item.relevant for item in items[:len(batch)]]
        flags += [True] * (len(batch) - len(flags))
        return flags

    return [item.relevant for item in items]


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

"""
LLM-based relevance filter for marketplace search results.

Two quality modes:

* ``"high"`` (default) — chain-of-thought: each product gets a short *reason*
  before the boolean verdict.  More accurate, slightly slower due to extra tokens.
* ``"low"`` — flat boolean list only.  Faster, fewer output tokens.

Both modes run all batches **concurrently** (asyncio.gather + semaphore).
Prompts are in English — compact models handle English more reliably than Russian.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Literal

from ollama import AsyncClient
from pydantic import BaseModel, Field

from src.config import ollama_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_HIGH = """\
You are a strict product relevance filter for marketplace search results.

RULES (apply all strictly):

1. EXACT model match.
   If the query contains a specific model number — every digit and letter must
   match EXACTLY.  A different suffix, series letter, or generation number means
   no match.
   Examples of rejection:
     query "Keychron Q5"  → "Keychron Q5 Max", "Keychron Q5 HE", "Keychron V5" — NO MATCH
     query "Keychron Q5 Max" → "Keychron Q5 HE" — NO MATCH; "Keychron Q5 Max" — MATCH
     query "Samsung A54"  → "Samsung A56", "Samsung A55", "Samsung A36" — NO MATCH

2. EXACT brand match.
   If the query specifies a brand, the product brand must match (case-insensitive).
   Example: query "Keychron Q5" → product by INOI or with no brand — NO MATCH.

3. Product only — NO accessories.
   Reject cases, films, screen protectors, cables, stands, keycaps, and any other
   accessories, even if the target model name appears in their title.
   Example: "Screen protector for Samsung A54" — REJECT.
   Example: "Case for Keychron Q5" — REJECT.
   Example: "Keycap set compatible with Q5" — REJECT.

4. If the query contains no brand or model, evaluate by product type only.

For each product: write a brief reason (≤8 words) in field "reason",
then set "relevant" to true or false.\
"""

_SYSTEM_PROMPT_LOW = """\
You are a product relevance filter for marketplace search results.
For each product decide if it matches the user query.

Rules:
- Model number must match exactly (same digits AND letters). Different suffix = no match.
- Brand must match if specified in the query.
- Accessories (cases, films, cables, keycaps, stands) are NEVER relevant,
  even when they mention the exact model name.
- Return exactly one boolean per product, preserving input order.\
"""

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class RelevanceItem(BaseModel):
    """Single verdict with chain-of-thought reason (high-quality mode)."""

    reason: Annotated[
        str,
        Field(description="Brief reason for the decision (≤8 words)."),
    ]
    relevant: Annotated[
        bool,
        Field(description="True if the product matches the query."),
    ]


class RelevanceBatchHigh(BaseModel):
    """Structured output for high-quality mode."""

    results: Annotated[
        list[RelevanceItem],
        Field(description="Verdict for each product, in the same order as the input."),
    ]


class RelevanceBatchLow(BaseModel):
    """Structured output for fast mode — boolean flags only."""

    results: Annotated[
        list[bool],
        Field(description="Relevance flag for each product, in the same order as the input."),
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def filter_relevant(
    query: str,
    products: list[dict],
    *,
    quality: Literal["high", "low"] = "high",
) -> list[dict]:
    """
    Filter *products* to those relevant to *query* using a local Ollama model.

    Batches are scored **concurrently** (up to ``ollama_settings.concurrency``
    parallel requests) so total latency ≈ slowest single batch, not the sum.

    Falls back to returning all products unchanged on Ollama errors.

    Args:
        query:    The user's original search query.
        products: Raw product dicts (must have at least a ``name`` key).
        quality:  ``"high"`` — chain-of-thought, more accurate, slightly more tokens.
                  ``"low"``  — flat boolean list, faster, fewer output tokens.

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

    semaphore = asyncio.Semaphore(ollama_settings.concurrency)
    score_fn = _score_batch_high if quality == "high" else _score_batch_low

    async def _score_with_sem(batch: list[dict]) -> list[bool]:
        async with semaphore:
            return await score_fn(query, batch)

    batch_flags: list[list[bool]] = await asyncio.gather(
        *(_score_with_sem(b) for b in batches)
    )

    kept: list[dict] = []
    for batch, flags in zip(batches, batch_flags):
        for product, relevant in zip(batch, flags):
            if relevant:
                kept.append(product)

    logger.info(
        "Relevance filter [%s]: %d/%d products kept for query %r",
        quality,
        len(kept),
        len(products),
        query,
    )
    return kept


# ---------------------------------------------------------------------------
# Internal batch scorers
# ---------------------------------------------------------------------------


def _build_user_message(query: str, batch: list[dict]) -> str:
    numbered = "\n".join(
        f"{i + 1}. «{_product_label(p)}»" for i, p in enumerate(batch)
    )
    return (
        f"User query: «{query}»\n\n"
        f"Evaluate each product in order, return exactly {len(batch)} results:\n"
        f"{numbered}"
    )


async def _score_batch_high(query: str, batch: list[dict]) -> list[bool]:
    """High-quality scoring: chain-of-thought reason + boolean per item."""
    try:
        client = AsyncClient(host=ollama_settings.host, timeout=ollama_settings.timeout)
        response = await client.chat(
            model=ollama_settings.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT_HIGH},
                {"role": "user", "content": _build_user_message(query, batch)},
            ],
            format=RelevanceBatchHigh.model_json_schema(),
            options={"temperature": 0},
        )
        result = RelevanceBatchHigh.model_validate_json(response.message.content)
    except Exception as exc:
        logger.warning(
            "Ollama [high] failed for batch of %d (query=%r): %s — passing through",
            len(batch),
            query,
            exc,
        )
        return [True] * len(batch)

    for i, item in enumerate(result.results):
        logger.debug(
            "[high][%d] relevant=%s | %s | reason: %s",
            i + 1,
            item.relevant,
            _product_label(batch[i]) if i < len(batch) else "?",
            item.reason,
        )

    return _reconcile([item.relevant for item in result.results], expected=len(batch))


async def _score_batch_low(query: str, batch: list[dict]) -> list[bool]:
    """Fast scoring: flat boolean list, no reasoning overhead."""
    try:
        client = AsyncClient(host=ollama_settings.host, timeout=ollama_settings.timeout)
        response = await client.chat(
            model=ollama_settings.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT_LOW},
                {"role": "user", "content": _build_user_message(query, batch)},
            ],
            format=RelevanceBatchLow.model_json_schema(),
            options={"temperature": 0},
        )
        result = RelevanceBatchLow.model_validate_json(response.message.content)
    except Exception as exc:
        logger.warning(
            "Ollama [low] failed for batch of %d (query=%r): %s — passing through",
            len(batch),
            query,
            exc,
        )
        return [True] * len(batch)

    return _reconcile(result.results, expected=len(batch))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reconcile(flags: list[bool], expected: int) -> list[bool]:
    """Truncate or pad flag list to match the expected batch length."""
    if len(flags) == expected:
        return flags
    logger.warning(
        "Ollama returned %d flags for %d products — truncating/padding",
        len(flags),
        expected,
    )
    result = list(flags[:expected])
    result += [True] * (expected - len(result))
    return result


def _product_label(product: dict) -> str:
    """Build a compact display string from a product dict."""
    parts: list[str] = []
    brand = product.get("brand")
    if brand and str(brand).upper() not in ("N/A", "NONE", ""):
        parts.append(str(brand))
    name = product.get("name") or ""
    if name and name.upper() not in ("N/A", ""):
        parts.append(name)
    return " — ".join(parts) if parts else "(no name)"

"""
LLM-based relevance filter for marketplace search results.

Three quality modes:

* ``"high"`` (default) — chain-of-thought: each product gets a short *reason*
  before the boolean verdict.  More accurate, slightly slower due to extra tokens.
* ``"medium"`` — uses the detailed high-quality prompt but returns a flat boolean
  list.  Accurate like *high*, but faster due to fewer output tokens.
* ``"low"`` — flat boolean list with a simpler prompt.  Fastest, fewest output tokens.

All modes run all batches **concurrently** (asyncio.gather + semaphore).
Prompts are in English — compact models handle English more reliably than Russian.

A heuristic pre-filter rejects obvious mismatches (accessories, wrong brand)
*before* any LLM call, reducing the number of products the model must evaluate.
"""

from __future__ import annotations

import asyncio
import logging
import re
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
# Heuristic pre-filter
# ---------------------------------------------------------------------------

# Accessory keywords in Russian and English (lowercase)
_ACCESSORY_PATTERNS: set[str] = {
    # Russian
    "чехол", "чехлы", "бампер", "кейс",
    "пленка", "плёнка", "пленки", "плёнки",
    "защитное стекло", "защитная пленка", "защитная плёнка",
    "кабель", "провод", "зарядка", "зарядное",
    "подставка", "держатель", "крепление",
    "наклейка", "стикер",
    "ремешок", "браслет",
    # English
    "case", "cover", "bumper",
    "film", "screen protector", "tempered glass",
    "cable", "charger", "charging",
    "stand", "holder", "mount", "bracket",
    "keycap", "keycaps", "wrist rest",
    "sticker", "decal", "skin",
    "strap", "band",
}

# Precompiled regex: match any accessory keyword as a whole word
_ACCESSORY_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in _ACCESSORY_PATTERNS) + r")\b",
    re.IGNORECASE,
)

# Common "for model X" patterns that indicate an accessory
_FOR_MODEL_RE = re.compile(
    r"\b(?:для|for|compatible with|совместим|на)\b",
    re.IGNORECASE,
)


def _quick_reject(query: str, product: dict) -> bool | None:
    """Heuristic pre-filter. Returns False if obviously irrelevant, None if unsure.

    This catches accessories and obvious brand mismatches *before* the LLM,
    reducing the number of products the model must evaluate.
    """
    name = (product.get("name") or "").lower()
    if not name:
        return None  # no info to judge, let LLM decide

    # 1. Accessory detection: keyword + "for X" pattern
    if _ACCESSORY_RE.search(name) and _FOR_MODEL_RE.search(name):
        return False

    return None  # needs LLM


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
    quality: Literal["high", "medium", "low"] = "high",
) -> list[dict]:
    """
    Filter *products* to those relevant to *query* using a local Ollama model.

    A fast heuristic pre-filter rejects obvious mismatches (accessories, etc.)
    before batching the remainder for LLM scoring.

    Batches are scored **concurrently** (up to ``ollama_settings.concurrency``
    parallel requests) so total latency ≈ slowest single batch, not the sum.

    Falls back to returning all products unchanged on Ollama errors.

    Args:
        query:    The user's original search query.
        products: Raw product dicts (must have at least a ``name`` key).
        quality:  ``"high"``   — chain-of-thought, most accurate, most tokens.
                  ``"medium"`` — detailed prompt, flat boolean output, fast + accurate.
                  ``"low"``    — simple prompt, flat boolean output, fastest.

    Returns:
        Subset of *products* that the model judged relevant.
    """
    if not products:
        return products

    # ---- Phase 1: heuristic pre-filter ----
    needs_llm: list[tuple[int, dict]] = []  # (original_index, product)
    kept: list[dict] = []
    heuristic_rejected = 0

    for idx, product in enumerate(products):
        verdict = _quick_reject(query, product)
        if verdict is False:
            heuristic_rejected += 1
            logger.debug(
                "Heuristic rejected [%d]: %s",
                idx + 1,
                _product_label(product),
            )
        else:
            needs_llm.append((idx, product))

    if heuristic_rejected:
        logger.info(
            "Heuristic pre-filter: %d/%d products rejected for query %r",
            heuristic_rejected,
            len(products),
            query,
        )

    # ---- Phase 2: LLM scoring on remaining products ----
    if not needs_llm:
        return kept  # all rejected by heuristic

    llm_products = [p for _, p in needs_llm]

    batch_size = ollama_settings.batch_size
    batches = [
        llm_products[offset : offset + batch_size]
        for offset in range(0, len(llm_products), batch_size)
    ]

    semaphore = asyncio.Semaphore(ollama_settings.concurrency)
    score_fn = {
        "high": _score_batch_high,
        "medium": _score_batch_medium,
        "low": _score_batch_low,
    }[quality]

    async def _score_with_sem(batch: list[dict]) -> list[bool]:
        async with semaphore:
            return await score_fn(query, batch)

    batch_flags: list[list[bool]] = await asyncio.gather(
        *(_score_with_sem(b) for b in batches)
    )

    for batch, flags in zip(batches, batch_flags):
        for product, relevant in zip(batch, flags):
            if relevant:
                kept.append(product)

    logger.info(
        "Relevance filter [%s]: %d/%d products kept for query %r"
        " (heuristic_rejected=%d, llm_evaluated=%d)",
        quality,
        len(kept),
        len(products),
        query,
        heuristic_rejected,
        len(llm_products),
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


def _llm_options() -> dict:
    """Build the Ollama options dict with context/generation caps."""
    return {
        "temperature": 0,
        "num_ctx": ollama_settings.num_ctx,
        "num_predict": ollama_settings.num_predict,
    }


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
            options=_llm_options(),
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


async def _score_batch_medium(query: str, batch: list[dict]) -> list[bool]:
    """Medium-quality scoring: detailed prompt for accuracy, flat boolean output for speed."""
    try:
        client = AsyncClient(host=ollama_settings.host, timeout=ollama_settings.timeout)
        response = await client.chat(
            model=ollama_settings.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT_HIGH},
                {"role": "user", "content": _build_user_message(query, batch)},
            ],
            format=RelevanceBatchLow.model_json_schema(),
            options=_llm_options(),
        )
        result = RelevanceBatchLow.model_validate_json(response.message.content)
    except Exception as exc:
        logger.warning(
            "Ollama [medium] failed for batch of %d (query=%r): %s — passing through",
            len(batch),
            query,
            exc,
        )
        return [True] * len(batch)

    return _reconcile(result.results, expected=len(batch))


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
            options=_llm_options(),
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

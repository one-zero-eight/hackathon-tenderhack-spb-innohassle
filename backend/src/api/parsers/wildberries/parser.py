from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import quote_plus

from playwright.async_api import BrowserContext, Page

from src.api.parsers.cloak_browser import (
    CloakSessionConfig,
    close_cloak_session,
    new_pool_profile_dir,
    open_cloak_session,
)
from src.api.parsers.playwright_page import evaluate, goto, page_blob, wait_for_function
from src.api.parsers.price_utils import parse_rub_price
from src.api.parsers.wildberries.dom_extract import (
    CARDS_READY_SCRIPT,
    WB_BATCH_PAUSE_SEC,
    WB_CARD_COUNT_SCRIPT,
    WB_EXTRACT_ALL_CARDS_JS,
    WB_SCROLL_JS,
    WB_SCROLL_PAUSE_SEC,
)
from src.api.parsers.wildberries.exceptions import WildberriesAccessError
from src.api.parsers.wildberries.search_api import split_brand_from_name

logger = logging.getLogger(__name__)

WB_HOME = "https://www.wildberries.ru/"
WB_SEARCH = "https://www.wildberries.ru/catalog/0/search.aspx?search="
WB_STREAM_BATCH_SIZE = 10

CHALLENGE_MARKERS = ("почти готов",)
HARD_BLOCK_MARKERS = (
    "captcha",
    "доступ ограничен",
    "подтвердите",
    "не робот",
    "429 too many",
)


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    return " ".join(value.split()) or None


class WildberriesParser:
    """Wildberries via CloakBrowser: search.aspx SERP, scroll, extract product cards from DOM."""

    def __init__(
        self,
        *,
        headless: bool = True,
        proxy: str | None = None,
        geoip: bool = True,
        humanize: bool = False,
        page_load_timeout: int | None = None,
        element_wait_timeout: int = 8,
        page_load_retries: int = 1,
        keep_alive: bool = False,
        profile_dir: Path | None = None,
    ) -> None:
        self.headless = headless
        self.proxy = proxy
        self.geoip = geoip
        self.humanize = humanize
        self.keep_alive = keep_alive
        self.page_load_timeout = page_load_timeout
        self.element_wait_timeout = element_wait_timeout
        self.page_load_retries = max(page_load_retries, 1)
        self._profile_dir = profile_dir
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._bridge_upstream: str | None = None

    async def __aenter__(self) -> WildberriesParser:
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close(force=True)

    async def start(self) -> None:
        profile = self._profile_dir
        if self.keep_alive and profile is None:
            profile = new_pool_profile_dir("wb")
        config = CloakSessionConfig(
            headless=self.headless,
            proxy=self.proxy,
            geoip=self.geoip and bool(self.proxy),
            humanize=self.humanize,
            user_data_dir=profile if self.keep_alive else None,
        )
        self._context, self._page, self._bridge_upstream = await open_cloak_session(config)

    async def close(self, *, force: bool = False) -> None:
        await close_cloak_session(
            self._context,
            keep_alive=self.keep_alive and not force,
            bridge_upstream=self._bridge_upstream if force or not self.keep_alive else None,
        )
        self._context = None
        self._page = None
        self._bridge_upstream = None

    @property
    def _p(self) -> Page:
        if not self._page:
            raise RuntimeError("CloakBrowser page is not started")
        return self._page

    def _nav_timeout(self) -> float:
        return float(self.page_load_timeout or 25)

    async def _sleep(self, min_sec: float, max_sec: float | None = None) -> None:
        await asyncio.sleep(random.uniform(min_sec, max_sec or min_sec))

    async def _is_blocked(self) -> bool:
        try:
            title = (await self._p.title()).lower()
        except Exception:
            return True
        blob = await page_blob(self._p)
        if any(m in title for m in HARD_BLOCK_MARKERS):
            return True
        if any(m in blob for m in HARD_BLOCK_MARKERS):
            return True
        return False

    async def _is_challenge_page(self) -> bool:
        try:
            title = (await self._p.title()).lower()
        except Exception:
            return True
        return any(m in title for m in CHALLENGE_MARKERS)

    async def _wait_past_challenge(self, timeout: float) -> bool:
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            if await self._is_blocked():
                return False
            if not await self._is_challenge_page():
                return True
            await asyncio.sleep(0.4)
        return not await self._is_challenge_page()

    async def _apply_dest_cookies(self, dest: int) -> None:
        if not self._context:
            return
        geo_value = json.dumps({"id": dest})
        for name in ("wbx-geo", "GeoIdsJson"):
            await self._context.add_cookies(
                [
                    {
                        "name": name,
                        "value": geo_value,
                        "domain": ".wildberries.ru",
                        "path": "/",
                    },
                ],
            )

    async def _count_product_cards(self) -> int:
        count = await evaluate(self._p, WB_CARD_COUNT_SCRIPT)
        return int(count) if isinstance(count, (int, float)) else 0

    def _scroll_rounds_for_target(self, target: int) -> int:
        items_per_scroll = 6
        rounds = (target + items_per_scroll - 1) // items_per_scroll + 2
        return max(5, min(rounds, 35))

    async def warmup_session(self) -> None:
        logger.info("Wildberries session warmup (CloakBrowser DOM)")
        await goto(self._p, WB_HOME, timeout_sec=self._nav_timeout(), retries=2)
        await self._sleep(0.5, 1.0)
        if await self._is_challenge_page():
            await self._wait_past_challenge(max(float(self.element_wait_timeout) * 2, 20.0))

    async def _open_search_page(self, keyword: str, *, dest: int) -> None:
        search_url = f"{WB_SEARCH}{quote_plus(keyword)}&dest={dest}"
        challenge_timeout = max(float(self.element_wait_timeout) * 2, 20.0)
        cards_timeout = min(max(float(self.element_wait_timeout), 8.0), 15.0)
        attempts = max(self.page_load_retries, 2)
        last_title = ""

        for attempt in range(1, attempts + 1):
            await self._apply_dest_cookies(dest)
            await goto(self._p, search_url, timeout_sec=self._nav_timeout(), retries=2)
            await self._sleep(1.2, 2.0)
            last_title = await self._p.title()

            if await self._is_blocked():
                logger.warning(
                    "WB search blocked (title=%r, attempt %d/%d)",
                    last_title,
                    attempt,
                    attempts,
                )
                if attempt < attempts:
                    await self._sleep(2.0, 3.0)
                    continue
                break

            if await self._is_challenge_page():
                logger.info(
                    "WB challenge (title=%r), waiting up to %.0fs",
                    last_title,
                    challenge_timeout,
                )
                if await self._wait_past_challenge(challenge_timeout):
                    pass
                elif attempt < attempts:
                    await self._sleep(2.0, 3.0)
                    continue
                else:
                    break

            try:
                await wait_for_function(
                    self._p,
                    CARDS_READY_SCRIPT,
                    timeout_sec=cards_timeout,
                    poll_interval_sec=0.25,
                )
                logger.info("WB SERP ready: %s (title=%r)", self._p.url, last_title)
                return
            except TimeoutError:
                logger.warning(
                    "WB search cards not ready (title=%r, attempt %d/%d)",
                    last_title,
                    attempt,
                    attempts,
                )
                if attempt < attempts:
                    await self._sleep(2.0, 3.0)

        raise WildberriesAccessError(
            f"anti-bot or empty page (title={last_title!r})",
            url=search_url,
        )

    def _raw_item_to_product(self, item: dict) -> dict | None:
        sale_price = parse_rub_price(item.get("priceText"))
        if sale_price is None:
            return None
        url = item.get("url")
        if isinstance(url, str) and url.startswith("/"):
            url = f"https://www.wildberries.ru{url}"
        name = _clean_text(item.get("name"))
        brand = _clean_text(item.get("brand"))
        brand, name = split_brand_from_name(name, brand)
        return {
            "name": name,
            "brand": brand,
            "sale_price": sale_price,
            "original_price": parse_rub_price(item.get("originalPriceText")),
            "url": url,
            "image_url": item.get("image_url"),
            "source": "Wildberries",
        }

    async def _extract_raw_cards(self) -> list[dict]:
        raw = await evaluate(self._p, WB_EXTRACT_ALL_CARDS_JS)
        return raw if isinstance(raw, list) else []

    async def _iter_products_from_dom(
        self,
        *,
        limit: int,
        skip: int,
        batch_size: int,
    ) -> AsyncIterator[list[dict]]:
        target_cards = skip + limit
        max_rounds = self._scroll_rounds_for_target(target_cards)
        seen_keys: set[str] = set()
        skipped_count = 0
        emitted = 0
        pending: list[dict] = []
        stale = 0
        dom_batch_no = 0

        def drain_batches(*, force: bool = False) -> list[list[dict]]:
            nonlocal pending, dom_batch_no
            batches: list[list[dict]] = []
            while len(pending) >= batch_size:
                dom_batch_no += 1
                chunk = pending[:batch_size]
                pending = pending[batch_size:]
                logger.info("WB DOM batch %d: %d products", dom_batch_no, len(chunk))
                batches.append(chunk)
            if force and pending:
                dom_batch_no += 1
                logger.info("WB DOM batch %d: %d products (final)", dom_batch_no, len(pending))
                batches.append(pending)
                pending = []
            return batches

        for rnd in range(max_rounds):
            prev_seen = len(seen_keys)
            for item in await self._extract_raw_cards():
                if not isinstance(item, dict):
                    continue
                product = self._raw_item_to_product(item)
                if product is None:
                    continue
                key = product.get("url") or str(product.get("name"))
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                if skipped_count < skip:
                    skipped_count += 1
                    continue
                if emitted >= limit:
                    for batch in drain_batches(force=True):
                        yield batch
                    return

                pending.append(product)
                emitted += 1
                for batch in drain_batches():
                    yield batch
                if emitted >= limit:
                    for batch in drain_batches(force=True):
                        yield batch
                    return

            new_cards = len(seen_keys) - prev_seen
            if new_cards == 0:
                stale += 1
            else:
                stale = 0
                logger.info(
                    "WB DOM scroll round %d: +%d cards (%d/%d in DOM, emitted %d/%d)",
                    rnd,
                    new_cards,
                    await self._count_product_cards(),
                    target_cards,
                    emitted,
                    limit,
                )

            if emitted >= limit:
                break
            if stale >= 4:
                logger.info(
                    "WB DOM scroll stopped: %d products (no new cards, round %d)",
                    emitted,
                    rnd,
                )
                break
            if rnd + 1 < max_rounds:
                await evaluate(self._p, WB_SCROLL_JS)
                await self._sleep(*WB_SCROLL_PAUSE_SEC)

        for batch in drain_batches(force=True):
            yield batch

    async def iter_products(
        self,
        keyword: str,
        limit: int,
        *,
        skip: int = 0,
        dest: int = -1257786,
        batch_size: int = WB_STREAM_BATCH_SIZE,
    ) -> AsyncIterator[list[dict]]:
        logger.info("Wildberries DOM stream: %r (dest=%d, limit=%d)", keyword, dest, limit)
        await self._open_search_page(keyword, dest=dest)

        emitted = 0
        async for batch in self._iter_products_from_dom(
            limit=limit,
            skip=skip,
            batch_size=batch_size,
        ):
            emitted += len(batch)
            yield batch

        logger.info(
            "Wildberries DOM stream done for %r: %d products (limit=%d)",
            keyword,
            emitted,
            limit,
        )

    async def run(
        self,
        keyword: str,
        limit: int,
        *,
        skip: int = 0,
        dest: int = -1257786,
    ) -> list[dict]:
        products: list[dict] = []
        async for batch in self.iter_products(keyword, limit, skip=skip, dest=dest, batch_size=limit):
            products.extend(batch)
        return products[:limit]


WildberriesSeleniumParser = WildberriesParser

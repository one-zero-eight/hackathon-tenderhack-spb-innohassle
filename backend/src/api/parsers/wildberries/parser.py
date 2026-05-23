from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import AsyncIterator
from urllib.parse import quote_plus

from selenium_driverless.webdriver import Chrome

from src.api.parsers.price_utils import parse_rub_price
from src.api.parsers.wait import safe_execute_script, wait_for_script_true
from src.api.parsers.wildberries.browser import create_driverless_driver
from src.api.parsers.wildberries.exceptions import WildberriesAccessError
from src.api.parsers.wildberries.navigation import safe_get
from src.api.parsers.wildberries.search_api import iter_products_via_browser_api

logger = logging.getLogger(__name__)

WB_STREAM_BATCH_SIZE = 10
WB_HOME = "https://www.wildberries.ru/"
WB_SEARCH = "https://www.wildberries.ru/catalog/0/search.aspx?search="
CHALLENGE_MARKERS = ("почти готов",)
HARD_BLOCK_MARKERS = (
    "captcha",
    "доступ ограничен",
    "подтвердите",
    "не робот",
)
CARDS_READY_SCRIPT = (
    "return document.querySelectorAll('article, .product-card, [data-nm-id]').length > 0;"
)
WB_CARD_COUNT_SCRIPT = (
    "return document.querySelectorAll('article, .product-card, [data-nm-id]').length;"
)
# Plain statements only: Selenium prepends "return", so "() => {}" becomes invalid JS.
WB_SCROLL_JS = """
const cards = document.querySelectorAll(
  '.product-card__wrapper, article.product-card, article[data-nm-id], [data-nm-id]'
);
const last = cards[cards.length - 1];
if (last) {
  last.scrollIntoView({ block: 'end', behavior: 'instant' });
} else {
  window.scrollBy(0, Math.max(window.innerHeight * 0.9, 900));
}
window.dispatchEvent(new Event('scroll'));
const list = document.querySelector(
  '.product-list, .catalog-page__content, .catalog-page, main'
);
if (list && list.scrollHeight > list.clientHeight + 40) {
  list.scrollTop = list.scrollHeight;
}
"""
WB_EXTRACT_JS = """
const limit = arguments[0];
const skip = arguments[1];
const pickText = (root, sel) => {
  const el = root.querySelector(sel);
  return el ? el.innerText.trim() : null;
};
const pickAttr = (root, sel, attr) => {
  const el = root.querySelector(sel);
  if (!el) return null;
  return el.getAttribute(attr) || null;
};
const pickPrice = (card) => {
  const sels = [
    "ins.price__lower-price",
    ".price__lower-price",
    ".product-card__price",
    ".price__wrap",
    "span[class*='price__lower']",
    "span[class*='price']",
  ];
  for (const sel of sels) {
    const el = card.querySelector(sel);
    if (el) {
      const t = el.innerText.trim();
      if (/\\d/.test(t)) return t;
    }
  }
  const m = (card.innerText || "").match(/(\\d[\\d\\s\\u00a0]*)\\s*₽/);
  return m ? m[0].trim() : null;
};
const pickOriginalPrice = (card) => {
  const el = card.querySelector(
    "del, .price__old, .product-card__price-old, span[class*='price-old'], span[class*='old-price']"
  );
  if (!el) return null;
  const t = el.innerText.trim();
  return /\\d/.test(t) ? t : null;
};
const cards = document.querySelectorAll("article, .product-card, [data-nm-id]");
const out = [];
for (const card of cards) {
  const priceText = pickPrice(card);
  const link = pickAttr(card, "a.product-card__link, a[href*='/catalog/']", "href");
  const imageUrl = pickAttr(card, "img", "src") || pickAttr(card, "img", "data-src");
  let name = pickText(card, ".product-card__name, .goods-name, [class*='product-card__name']");
  if (name) name = name.replace(/^\\//, "").trim();
  out.push({
    name,
    brand: pickText(card, ".product-card__brand, .brand-name, [class*='brand']"),
    priceText,
    originalPriceText: pickOriginalPrice(card),
    url: link,
    image_url: imageUrl,
  });
}
return out.slice(skip, skip + limit);
"""


class WildberriesSeleniumParser:
    def __init__(
        self,
        *,
        headless: bool = True,
        page_load_timeout: int | None = None,
        element_wait_timeout: int = 45,
        page_load_retries: int = 3,
        keep_alive: bool = False,
    ) -> None:
        self.headless = headless
        self.page_load_timeout = page_load_timeout
        self.element_wait_timeout = element_wait_timeout
        self.page_load_retries = page_load_retries
        self.keep_alive = keep_alive
        self.driver: Chrome | None = None
        self.user_agent: str | None = None

    async def __aenter__(self) -> WildberriesSeleniumParser:
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def start(self) -> None:
        self.driver, self.user_agent = await create_driverless_driver(headless=self.headless)

    async def close(self, *, force: bool = False) -> None:
        if self.keep_alive and not force:
            return
        if self.driver:
            await self.driver.quit()
            self.driver = None

    @property
    def _d(self) -> Chrome:
        if not self.driver:
            raise RuntimeError("Driver is not running")
        return self.driver

    async def _page_blob(self) -> str:
        title = (await self._d.title).lower()
        body = await safe_execute_script(
            self._d,
            "return document.body ? document.body.innerText : ''",
        )
        return f"{title} {(body or '').lower()}"

    async def _is_challenge_page(self) -> bool:
        blob = await self._page_blob()
        return any(marker in blob for marker in CHALLENGE_MARKERS)

    async def _is_hard_blocked(self) -> bool:
        blob = await self._page_blob()
        return any(marker in blob for marker in HARD_BLOCK_MARKERS)

    async def _apply_dest_cookies(self, dest: int) -> None:
        geo_cookie_value = json.dumps({"id": dest})
        for cookie_name in ("wbx-geo", "GeoIdsJson"):
            await self._d.add_cookie(
                {
                    "name": cookie_name,
                    "value": geo_cookie_value,
                    "domain": ".wildberries.ru",
                    "path": "/",
                },
            )

    async def _wait_past_challenge(self, timeout: float) -> bool:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if await self._is_hard_blocked():
                return False
            if not await self._is_challenge_page():
                return True
            await asyncio.sleep(0.4)
        return not await self._is_challenge_page()

    async def _wait_for_product_cards(self, timeout: float) -> bool:
        try:
            await wait_for_script_true(
                self._d,
                CARDS_READY_SCRIPT,
                timeout=timeout,
                poll_interval=0.25,
            )
            return True
        except TimeoutError:
            return False

    async def _count_product_cards(self) -> int:
        count = await safe_execute_script(self._d, WB_CARD_COUNT_SCRIPT)
        return int(count) if isinstance(count, int) else 0

    def _scroll_rounds_for_target(self, target: int) -> int:
        items_per_scroll = 6
        rounds = (target + items_per_scroll - 1) // items_per_scroll + 2
        return max(5, min(rounds, 35))

    async def _scroll_to_load_cards(self, target: int) -> int:
        """Scroll SERP until enough product cards are in the DOM (WB lazy-loads on scroll)."""
        max_rounds = self._scroll_rounds_for_target(target)
        stale = 0
        prev = 0

        for rnd in range(max_rounds):
            count = await self._count_product_cards()
            if count >= target:
                logger.info("WB scroll: %d cards in DOM (target %d, round %d)", count, target, rnd)
                return count

            if count == prev:
                stale += 1
            else:
                stale = 0
            prev = count

            if stale >= 2:
                logger.info(
                    "WB scroll stopped: %d cards in DOM (target %d, no new cards)",
                    count,
                    target,
                )
                break

            await safe_execute_script(self._d, WB_SCROLL_JS)
            await asyncio.sleep(random.uniform(0.45, 0.85))

        return prev

    async def warmup_session(self) -> None:
        challenge_timeout = max(float(self.element_wait_timeout) * 2, 20.0)
        logger.info("Wildberries session warmup")
        await safe_get(
            self._d,
            WB_HOME,
            page_load_timeout=self.page_load_timeout,
            retries=1,
            fast=True,
            wait_load=True,
        )
        if not await self._wait_past_challenge(challenge_timeout):
            title = await self._d.title
            logger.warning("WB warmup: challenge not cleared (title=%r)", title)

    async def _open_search_page(self, keyword: str, *, dest: int) -> None:
        search_url = f"{WB_SEARCH}{quote_plus(keyword)}&dest={dest}"
        challenge_timeout = max(float(self.element_wait_timeout) * 2, 20.0)
        cards_timeout = min(float(self.element_wait_timeout), 12.0)
        attempts = max(self.page_load_retries, 2)
        last_title = ""

        for attempt in range(1, attempts + 1):
            await safe_get(
                self._d,
                search_url,
                page_load_timeout=self.page_load_timeout,
                retries=1,
                fast=True,
                wait_load=True,
            )
            await self._apply_dest_cookies(dest)
            await safe_get(
                self._d,
                search_url,
                page_load_timeout=self.page_load_timeout,
                retries=1,
                fast=True,
                wait_load=True,
            )
            await asyncio.sleep(1.5)
            last_title = await self._d.title

            if await self._is_hard_blocked():
                break

            if await self._is_challenge_page():
                logger.info(
                    "WB challenge (title=%r), waiting up to %.0fs (attempt %d/%d)",
                    last_title,
                    challenge_timeout,
                    attempt,
                    attempts,
                )
                if not await self._wait_past_challenge(challenge_timeout):
                    last_title = await self._d.title
                    if attempt < attempts:
                        await asyncio.sleep(2)
                        continue
                    break

            if await self._wait_for_product_cards(cards_timeout):
                return

            logger.warning(
                "WB search not ready (title=%r, attempt %d/%d)",
                last_title,
                attempt,
                attempts,
            )
            if attempt < attempts:
                await asyncio.sleep(2)

        raise WildberriesAccessError(
            f"anti-bot or empty page (title={last_title!r})",
            url=search_url,
        )

    def _raw_item_to_product(self, item: dict) -> dict | None:
        sale_price = parse_rub_price(item.get("priceText"))
        if sale_price is None:
            return None
        url = item.get("url")
        if url and url.startswith("/"):
            url = f"https://www.wildberries.ru{url}"
        return {
            "name": item.get("name"),
            "brand": _clean_text(item.get("brand")),
            "sale_price": sale_price,
            "original_price": parse_rub_price(item.get("originalPriceText")),
            "url": url,
            "image_url": item.get("image_url"),
            "source": "Wildberries",
        }

    async def _extract_raw_cards(self) -> list[dict]:
        raw = await safe_execute_script(self._d, WB_EXTRACT_JS, 10_000, 0)
        return raw if isinstance(raw, list) else []

    async def _extract_products(self, limit: int, skip: int) -> list[dict]:
        raw = await safe_execute_script(self._d, WB_EXTRACT_JS, limit, skip)
        if not isinstance(raw, list):
            return []

        products: list[dict] = []
        for item in raw:
            product = self._raw_item_to_product(item)
            if product is None:
                continue
            products.append(product)
            if len(products) >= limit:
                break
        return products

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

        def drain_batches(*, force: bool = False) -> list[list[dict]]:
            nonlocal pending
            batches: list[list[dict]] = []
            while len(pending) >= batch_size:
                batches.append(pending[:batch_size])
                pending = pending[batch_size:]
            if force and pending:
                batches.append(pending)
                pending = []
            return batches

        for rnd in range(max_rounds):
            prev_seen = len(seen_keys)
            for item in await self._extract_raw_cards():
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
            if emitted >= limit:
                break
            if stale >= 4:
                logger.info(
                    "WB DOM scroll stopped at %d items (no new cards, round %d)",
                    emitted,
                    rnd,
                )
                break
            if rnd + 1 < max_rounds:
                await safe_execute_script(self._d, WB_SCROLL_JS)
                await asyncio.sleep(random.uniform(0.7, 1.2))

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
        logger.info("Wildberries stream: %r (dest=%d)", keyword, dest)
        await self._open_search_page(keyword, dest=dest)

        emitted = 0
        try:
            async for batch in iter_products_via_browser_api(
                self._d,
                keyword,
                limit,
                skip=skip,
                dest=dest,
                batch_size=batch_size,
            ):
                emitted += len(batch)
                yield batch
            if emitted > 0:
                logger.info(
                    "Wildberries stream done for %r (limit=%d): %d items (API)",
                    keyword,
                    limit,
                    emitted,
                )
                return
            logger.warning("WB search API returned 0 items for %r, trying DOM", keyword)
        except Exception as exc:
            logger.warning(
                "WB search API via browser failed for %r, DOM fallback: %s",
                keyword,
                exc,
            )

        emitted = 0
        async for batch in self._iter_products_from_dom(
            limit=limit,
            skip=skip,
            batch_size=batch_size,
        ):
            emitted += len(batch)
            yield batch

        logger.info(
            "Wildberries stream done for %r (limit=%d): %d items (DOM)",
            keyword,
            limit,
            emitted,
        )

    async def run(
        self,
        keyword: str,
        limit: int,
        *,
        skip: int = 0,
        dest: int = -1257786,
    ) -> list[dict]:
        logger.info("Wildberries search: %r (dest=%d)", keyword, dest)
        products: list[dict] = []
        async for batch in self.iter_products(keyword, limit, skip=skip, dest=dest, batch_size=limit):
            products.extend(batch)
        logger.info(
            "Wildberries parse done for %r (limit=%d): %d items",
            keyword,
            limit,
            len(products),
        )
        return products


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    return " ".join(value.split()) or None

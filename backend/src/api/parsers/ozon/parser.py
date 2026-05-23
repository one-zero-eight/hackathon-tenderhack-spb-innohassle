from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import time
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import quote

from playwright.async_api import BrowserContext, Page

from src.api.parsers.cloak_browser import (
    CloakSessionConfig,
    close_cloak_session,
    new_pool_profile_dir,
    open_cloak_session,
)
from src.api.parsers.geocoder import resolve_ozon_city
from src.api.parsers.ozon.composer_extract import (
    FETCH_COMPOSER_JS,
    composer_items_by_url,
    normalize_product_url,
    parse_composer_search,
)
from src.api.parsers.ozon.cookies_loader import apply_cookies_to_context
from src.api.parsers.ozon.exceptions import OzonAccessError
from src.api.parsers.ozon.models import ProductResult
from src.api.parsers.ozon.titles import pick_ozon_product_title
from src.api.parsers.playwright_page import (
    dismiss_buttons,
    evaluate,
    goto,
    page_blob,
    wait_for_function,
)

logger = logging.getLogger(__name__)

OZON_HOME = "https://www.ozon.ru/"
BLOCKED_MARKERS = (
    "antibot",
    "captcha",
    "доступ ограничен",
    "доступ запрещен",
    "подтвердите",
    "не робот",
    "похоже, нет соединения",
)
SERP_PRODUCTS_READY = "document.querySelectorAll(\"a[href*='/product/']\").length > 0"
EXTRACT_LISTING_JS = """
() => {
  const pickImage = (img) => {
    if (!img) return null;
    const src = img.currentSrc || img.src || img.getAttribute('data-src');
    return src && src.startsWith('http') && !src.startsWith('data:') ? src : null;
  };
  const pickPriceText = (root) => {
    const widgets = root.querySelectorAll(
      '[data-widget="price"], [data-widget="webPrice"], [data-widget="sku"], [data-testid*="price"], [class*="Price"]'
    );
    for (const w of widgets) {
      const t = (w.textContent || '').trim();
      if (/\\d/.test(t) && /₽|руб/i.test(t)) return t.slice(0, 80);
    }
    const spans = root.querySelectorAll('span, div');
    for (const el of spans) {
      const t = (el.textContent || '').trim();
      if (t.length > 32) continue;
      if (/\\d/.test(t) && /₽|руб/i.test(t)) return t.slice(0, 80);
    }
    const prices = [];
    const re = /([\\d\\s\\u00a0]{1,12})\\s*₽/g;
    let m;
    const blob = root.innerText || '';
    while ((m = re.exec(blob)) !== null) prices.push(m[0].trim());
    if (prices.length) return prices[0];
    const digits = blob.match(/([\\d\\s\\u00a0]{3,12})/g);
    if (digits) {
      for (const d of digits) {
        const n = d.replace(/\\D/g, '');
        if (n.length >= 3 && Number(n) >= 100) return `${d.trim()} ₽`;
      }
    }
    return null;
  };
  const pickOriginalPrice = (root) => {
    const el = root.querySelector(
      'del, span[class*="original"], span[class*="old-price"], span[style*="line-through"]'
    );
    if (!el) return null;
    const t = (el.textContent || '').trim();
    return /\\d/.test(t) ? t.slice(0, 80) : null;
  };
  const JUNK_TITLE = /^(распродажа|скидки?|акци[яи]|новинка|хит|бестселлер|выгодно|премиум|premium|оригинал|суперцена|завтра|осталось)$/i;
  const isTitleLine = (line) => {
    if (!line || line.length < 8) return false;
    if (/₽|руб/i.test(line)) return false;
    if (/^[\\d\\s%]+$/.test(line)) return false;
    if (JUNK_TITLE.test(line.trim())) return false;
    return true;
  };
  const pickTitle = (a, tile) => {
    const candidates = [];
    const titled = a.getAttribute('title')?.trim();
    if (isTitleLine(titled)) candidates.push(titled);
    const aria = a.getAttribute('aria-label')?.trim();
    if (isTitleLine(aria)) candidates.push(aria);
    for (const sel of [
      'span[class*="tile-title"]',
      'span[class*="tsBody500"]',
      'span[class*="tsBody"][class*="500"]',
      '[data-widget="searchResultsV2"] a span[class*="tsBody"]',
    ]) {
      const el = tile.querySelector(sel);
      if (!el) continue;
      const n = (el.textContent || '').trim();
      if (isTitleLine(n)) candidates.push(n);
    }
    const lines = (a.innerText || '').split('\\n').map((s) => s.trim()).filter(Boolean);
    for (const line of lines) {
      if (isTitleLine(line)) candidates.push(line);
    }
    if (!candidates.length) return '';
    return candidates.sort((x, y) => y.length - x.length)[0].slice(0, 500);
  };
  const out = [];
  const seen = new Set();
  for (const a of document.querySelectorAll("a[href*='/product/']")) {
    const href = a.href || a.getAttribute('href');
    if (!href || seen.has(href)) continue;
    seen.add(href);
    const tile =
      a.closest('[data-index]') ||
      a.closest('.tile-root') ||
      a.closest('[data-widget="searchResultsV2"] > div') ||
      a.closest('article') ||
      a.parentElement?.parentElement ||
      a;
    out.push({
      href,
      title: pickTitle(a, tile),
      price: pickPriceText(tile),
      originalPrice: pickOriginalPrice(tile),
      image: pickImage(tile.querySelector('img')),
    });
  }
  return out;
}
"""
FILL_SEARCH_INPUT_JS = """
(query) => {
  const input = document.querySelector(
    'input[name="text"], input[type="search"], [data-widget="searchBar"] input'
  );
  if (!input) return false;
  input.focus();
  input.value = query;
  input.dispatchEvent(new Event('input', { bubbles: true }));
  return true;
}
"""
SCROLL_STEP_JS = """
() => {
  const step = Math.max(window.innerHeight * 0.85, 700);
  const boxes = document.querySelectorAll(
    "[data-widget='searchResultsV2'], [data-widget='infiniteVirtualPaginator'], [data-widget='searchResults']"
  );
  for (const el of boxes) {
    if (el.scrollHeight > el.clientHeight + 40) {
      el.scrollTop += step;
      return;
    }
  }
  window.scrollBy(0, step);
}
"""


class OzonParser:
    """Async Ozon parser on CloakBrowser (stealth Chromium + Playwright API)."""

    def __init__(
        self,
        *,
        headless: bool = True,
        cookies_file: str | Path | None = None,
        proxy: str | None = None,
        geoip: bool = True,
        humanize: bool = False,
        scroll_pause: tuple[float, float] = (0.8, 1.2),
        slow_mode: bool = False,
        page_load_timeout: int | None = None,
        element_wait_timeout: int = 45,
        page_load_retries: int = 4,
        keep_alive: bool = False,
        profile_dir: Path | None = None,
    ) -> None:
        self.headless = headless
        self.cookies_file = cookies_file
        self.proxy = proxy
        self.geoip = geoip
        self.humanize = humanize
        self.slow_mode = slow_mode
        self.keep_alive = keep_alive
        self.page_load_timeout = page_load_timeout
        self.element_wait_timeout = element_wait_timeout
        self.page_load_retries = page_load_retries
        self._profile_dir = profile_dir
        if slow_mode:
            self.scroll_pause = (2.0, 3.0)
        elif keep_alive:
            self.scroll_pause = (0.2, 0.35)
        else:
            self.scroll_pause = scroll_pause
        if keep_alive and not slow_mode:
            self._nav_retries = max(page_load_retries, 2)
        elif slow_mode:
            self._nav_retries = page_load_retries
        else:
            self._nav_retries = min(page_load_retries, 2)
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._bridge_upstream: str | None = None
        self._cookies_path: Path | None = None

    async def __aenter__(self) -> OzonParser:
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close(force=True)

    async def start(self) -> None:
        profile = self._profile_dir
        if self.keep_alive and profile is None:
            profile = new_pool_profile_dir("ozon")
        config = CloakSessionConfig(
            headless=self.headless,
            proxy=self.proxy,
            geoip=self.geoip and bool(self.proxy),
            humanize=self.humanize,
            user_data_dir=profile if self.keep_alive else None,
        )
        self._context, self._page, self._bridge_upstream = await open_cloak_session(config)
        cookies_path = Path(self.cookies_file) if self.cookies_file else None
        if cookies_path and cookies_path.is_file():
            self._cookies_path = cookies_path.resolve()
            try:
                count = await apply_cookies_to_context(
                    self._context,
                    self._page,
                    self._cookies_path,
                    page_load_timeout=int(self.page_load_timeout or 20),
                )
                _log_cookie_session_hint(self._cookies_path, count)
            except Exception as exc:
                logger.error("Ozon cookies load failed (%s); continuing without cookies", exc)
                self._cookies_path = None

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

    async def _sleep(self, min_sec: float, max_sec: float | None = None) -> None:
        await asyncio.sleep(random.uniform(min_sec, max_sec or min_sec))

    async def _is_blocked(self) -> bool:
        blob = await page_blob(self._p)
        return any(marker in blob for marker in BLOCKED_MARKERS)

    def _nav_timeout(self, *, fast: bool) -> float:
        configured = float(self.page_load_timeout or 20)
        if fast:
            return min(configured, 28.0 if self.keep_alive else 12.0)
        return configured

    async def _reload_cookies(self) -> bool:
        if not self._cookies_path or not self._context or not self._page:
            return False
        try:
            count = await apply_cookies_to_context(
                self._context,
                self._page,
                self._cookies_path,
                page_load_timeout=int(self.page_load_timeout or 20),
            )
            logger.info("Ozon cookies reloaded: %d from %s", count, self._cookies_path.name)
            return True
        except Exception as exc:
            logger.error("Ozon cookies reload failed: %s", exc)
            return False

    async def _goto(
        self,
        url: str,
        *,
        fast: bool | None = None,
        cookies_retry: bool = True,
    ) -> None:
        use_fast = self.keep_alive and not self.slow_mode if fast is None else fast
        await goto(
            self._p,
            url,
            timeout_sec=self._nav_timeout(fast=use_fast),
            wait_until="commit" if use_fast else "domcontentloaded",
            retries=self._nav_retries,
        )
        await self._wait_serp_settled()
        if self.slow_mode:
            await self._sleep(2.0, 3.0)
        elif not self.keep_alive:
            await self._sleep(0.3, 0.5)
        if await self._is_blocked():
            if cookies_retry and await self._reload_cookies():
                logger.warning("Ozon blocked at %s — retrying after cookie reload", url)
                await self._goto(url, fast=fast, cookies_retry=False)
                return
            raise OzonAccessError(
                f"Ozon ограничил доступ: {url}. Проверьте proxy/cookies (CloakBrowser).",
                url=url,
            )

    async def warmup_session(self) -> None:
        logger.info("Ozon session warmup")
        await self._goto(OZON_HOME, fast=True, cookies_retry=False)
        await self._dismiss_overlays()
        if await self._is_blocked():
            logger.warning("Ozon warmup: blocked (%s)", await self._page_context())
            if await self._reload_cookies():
                await self._goto(OZON_HOME, fast=True, cookies_retry=False)
                await self._dismiss_overlays()

    async def _page_context(self) -> str:
        try:
            return f"title={await self._p.title()!r} url={self._p.url}"
        except Exception:
            return "title/url unavailable"

    async def _dismiss_overlays(self) -> None:
        await dismiss_buttons(self._p, ("OK", "Понятно", "Принять"))

    def _serp_wait_timeout(self) -> float:
        base = float(self.element_wait_timeout)
        if self.keep_alive and not self.slow_mode:
            return min(max(base, 4.0), 12.0)
        return min(max(base, 10.0), 15.0)

    async def _wait_serp_ready(self, timeout: float) -> None:
        await wait_for_function(self._p, SERP_PRODUCTS_READY, timeout_sec=timeout, poll_interval_sec=0.15)

    async def _wait_serp_settled(self) -> None:
        timeout_ms = 5_000 if self.keep_alive and not self.slow_mode else 8_000
        try:
            await self._p.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
        except Exception:
            pass
        if self.keep_alive and not self.slow_mode:
            await self._sleep(0.05, 0.12)
        else:
            await self._sleep(0.15, 0.3)

    def _is_on_ozon(self) -> bool:
        try:
            return "ozon.ru" in (self._p.url or "")
        except Exception:
            return False

    async def _apply_delivery_city(self, city: str) -> None:
        if city == "Москва":
            return
        logger.info("Ozon: setting delivery city to %r", city)
        await self._goto(OZON_HOME, fast=False)
        await self._dismiss_overlays()
        try:
            address = self._p.locator(
                '[data-widget="addressBookBar"], [data-widget="commonAddressBook"]'
            ).first
            await address.click(timeout=8000)
            await self._sleep(0.3, 0.5)
            field = self._p.locator(
                'input[placeholder*="город"], input[placeholder*="Населен"], input[type="search"]'
            ).first
            await field.fill(city, timeout=5000)
            await self._sleep(0.4, 0.7)
            await self._p.get_by_text(city, exact=False).first.click(timeout=5000)
            await self._sleep(0.5, 0.8)
            await self._wait_serp_settled()
        except Exception as exc:
            logger.warning("Ozon failed to set delivery city %r: %s", city, exc)

    async def search(self, query: str) -> None:
        logger.info("Поиск: %s", query)
        search_url = f"{OZON_HOME}search/?text={quote(query)}&from_global=true"
        cards_timeout = self._serp_wait_timeout()

        # Pooled sessions: search via homepage input (less aggressive than direct SERP URL).
        if self.keep_alive and not self.slow_mode:
            try:
                await self._search_via_input(query)
                return
            except OzonAccessError:
                raise
            except Exception as exc:
                logger.warning(
                    "Ozon search via input failed (%s), trying direct SERP URL",
                    exc,
                )

        for attempt in range(1, 3):
            logger.info("Ozon SERP load attempt %d/2", attempt)
            await self._goto(search_url)
            await self._dismiss_overlays()
            if await self._is_blocked():
                raise OzonAccessError(
                    f"Ozon ограничил доступ при поиске ({await self._page_context()})",
                    url=search_url,
                )
            try:
                await self._wait_serp_ready(cards_timeout)
                await self._wait_serp_settled()
                return
            except TimeoutError:
                logger.warning(
                    "Ozon SERP not ready (%s, attempt %d/2)",
                    await self._page_context(),
                    attempt,
                )
                if attempt < 2:
                    await asyncio.sleep(0.4)

        if not self.keep_alive:
            await self._search_via_input(query)
            return

        if await self._is_blocked():
            raise OzonAccessError(
                f"Ozon ограничил доступ ({await self._page_context()})",
                url=search_url,
            )
        raise OzonAccessError(
            f"Ozon: товары в выдаче не появились ({await self._page_context()})",
            url=search_url,
        )

    async def _try_fill_search_input(self, query: str) -> bool:
        filled = await evaluate(self._p, FILL_SEARCH_INPUT_JS, query)
        if filled:
            await self._sleep(0.2, 0.4)
            await self._p.keyboard.press("Enter")
            return True
        try:
            field = self._p.locator(
                'input[name="text"], input[type="search"], [data-widget="searchBar"] input'
            ).first
            await field.wait_for(state="visible", timeout=int(min(self.element_wait_timeout, 8) * 1000))
            await field.fill(query)
            await self._p.keyboard.press("Enter")
            return True
        except Exception:
            return False

    async def _search_via_input(self, query: str) -> None:
        serp_timeout = self._serp_wait_timeout()
        use_fast = self.keep_alive and not self.slow_mode
        if not self._is_on_ozon():
            await self._goto(OZON_HOME, fast=use_fast)
        await self._dismiss_overlays()
        if await self._is_blocked():
            raise OzonAccessError(f"Ozon ограничил доступ ({await self._page_context()})")
        if not await self._try_fill_search_input(query):
            raise OzonAccessError("Поле поиска не найдено")
        if use_fast:
            await self._sleep(0.25, 0.45)
        else:
            await self._sleep(0.5, 0.9)
        await self._wait_serp_ready(serp_timeout)
        await self._wait_serp_settled()

    async def _scroll_step(self) -> None:
        await evaluate(self._p, SCROLL_STEP_JS)
        await self._sleep(*self.scroll_pause)

    def _normalize_url(self, href: str) -> str | None:
        return normalize_product_url(href)

    async def _fetch_composer_by_url(self) -> dict[str, dict]:
        payload = await evaluate(self._p, FETCH_COMPOSER_JS)
        items = parse_composer_search(payload)
        if items:
            logger.info("Ozon composer-api: %d products", len(items))
        return composer_items_by_url(items)

    def _enrich_listing_item(self, item: dict, composer_by_url: dict[str, dict]) -> dict:
        url = item.get("url")
        if not url:
            return item
        composer = composer_by_url.get(url)
        if not composer:
            return item
        merged = {**item}
        if not merged.get("price"):
            merged["price"] = composer.get("price")
        if not merged.get("originalPrice"):
            merged["originalPrice"] = composer.get("originalPrice")
        dom_title = merged.get("title")
        composer_title = composer.get("title")
        merged["title"] = (
            pick_ozon_product_title(composer_title, dom_title)
            or composer_title
            or dom_title
            or "Без названия"
        )
        if not merged.get("image"):
            merged["image"] = composer.get("image")
        return merged

    async def _extract_from_listing(self) -> list[dict]:
        raw = await evaluate(self._p, EXTRACT_LISTING_JS)
        return raw if isinstance(raw, list) else []

    def _scroll_rounds_for_limit(self, limit: int) -> int:
        items_per_scroll = 8
        rounds = (limit + items_per_scroll - 1) // items_per_scroll + 2
        return max(3, min(rounds, 30))

    def _listing_from_composer(self, url: str, composer: dict) -> dict:
        return {
            "url": url,
            "title": composer.get("title") or "Без названия",
            "price": composer.get("price"),
            "originalPrice": composer.get("originalPrice"),
            "image": composer.get("image"),
        }

    async def collect_products_batched(
        self,
        limit: int,
        *,
        batch_size: int = 10,
    ) -> AsyncIterator[list[dict]]:
        collect_started = time.perf_counter()
        ordered: list[dict] = []
        seen: set[str] = set()
        stale = 0
        prev_total = 0
        last_sent = 0
        max_rounds = self._scroll_rounds_for_limit(limit)

        await self._wait_serp_settled()

        composer_by_url: dict[str, dict] = {}
        composer_started = time.perf_counter()
        try:
            composer_by_url = await self._fetch_composer_by_url()
        except Exception as exc:
            logger.warning("Ozon composer-api fetch failed: %s", exc)
        composer_sec = time.perf_counter() - composer_started

        def emit_pending(force: bool = False) -> list[list[dict]]:
            nonlocal last_sent
            batches: list[list[dict]] = []
            while len(ordered) - last_sent >= batch_size:
                chunk = ordered[last_sent : last_sent + batch_size]
                last_sent += batch_size
                batches.append(chunk)
            if force and last_sent < len(ordered):
                chunk = ordered[last_sent:]
                last_sent = len(ordered)
                batches.append(chunk)
            return batches

        if len(composer_by_url) >= limit:
            for url, composer in composer_by_url.items():
                if url in seen:
                    continue
                seen.add(url)
                ordered.append(self._listing_from_composer(url, composer))
                if len(ordered) >= limit:
                    break
            for batch in emit_pending(force=True):
                yield batch
            logger.info(
                "Ozon collect: composer-only %d/%d items in %.2fs (composer-api %.2fs, no scroll)",
                len(ordered),
                limit,
                time.perf_counter() - collect_started,
                composer_sec,
            )
            return

        logger.info(
            "Ozon collect: DOM scroll for %d items (composer had %d, up to %d rounds)",
            limit,
            len(composer_by_url),
            max_rounds,
        )

        for rnd in range(max_rounds):
            if rnd > 0 and await self._is_blocked():
                if ordered:
                    logger.warning("Блокировка после %d товаров", len(ordered))
                    break
                raise OzonAccessError("Блокировка при загрузке выдачи")

            for item in await self._extract_from_listing():
                url = self._normalize_url(item.get("href", ""))
                if not url or url in seen:
                    continue
                seen.add(url)
                row = self._enrich_listing_item({**item, "url": url}, composer_by_url)
                ordered.append(row)
                if len(ordered) >= limit:
                    for batch in emit_pending(force=True):
                        yield batch
                    return

            if composer_by_url and len(ordered) < limit:
                for url, composer in composer_by_url.items():
                    if url in seen:
                        continue
                    seen.add(url)
                    ordered.append(self._listing_from_composer(url, composer))
                    if len(ordered) >= limit:
                        for batch in emit_pending(force=True):
                            yield batch
                        return

            for batch in emit_pending():
                yield batch

            if len(ordered) == prev_total:
                stale += 1
            else:
                stale = 0
            prev_total = len(ordered)

            if stale >= 1:
                await evaluate(self._p, "() => window.scrollTo(0, document.body.scrollHeight)")
                await self._sleep(0.4, 0.6)
                stale = 0
                continue

            if rnd + 1 < max_rounds:
                await self._scroll_step()

        for batch in emit_pending(force=True):
            yield batch

        logger.info(
            "Ozon collect: finished %d/%d items in %.2fs (composer-api %.2fs, %d scroll rounds)",
            len(ordered),
            limit,
            time.perf_counter() - collect_started,
            composer_sec,
            max_rounds,
        )

    async def collect_products(self, limit: int) -> list[dict]:
        items: list[dict] = []
        async for batch in self.collect_products_batched(limit, batch_size=limit):
            items.extend(batch)
        return items[:limit]

    async def _parse_product_page(self, url: str, listing: dict, position: int) -> ProductResult:
        logger.info("[%d] Карточка: %s", position, url)
        title = listing.get("title") or "Без названия"
        price = listing.get("price")
        image = listing.get("image")
        description = None

        try:
            await self._goto(url, fast=False)
            title = await evaluate(
                self._p,
                "() => { const h = document.querySelector('h1'); return h ? h.innerText.trim() : null; }",
            ) or title

            price_text = await evaluate(
                self._p,
                """
                () => {
                  for (const sel of ["[data-widget='webPrice']", "span[class*='price']"]) {
                    const el = document.querySelector(sel);
                    if (el && /\\d/.test(el.innerText)) return el.innerText.trim();
                  }
                  return null;
                }
                """,
            )
            if price_text:
                price = re.sub(r"\s+", " ", str(price_text))

            image = await evaluate(
                self._p,
                """
                () => {
                  const og = document.querySelector("meta[property='og:image']");
                  if (og && og.content) return og.content;
                  const img = document.querySelector("img[src*='ir.ozone.ru']");
                  return img ? (img.src || img.getAttribute('src')) : null;
                }
                """,
            ) or image

            description = await evaluate(
                self._p,
                """
                () => {
                  const el = document.querySelector("[data-widget='webDescription']");
                  if (el && el.innerText.length > 30) return el.innerText.trim();
                  const meta = document.querySelector('meta[name="description"]');
                  return meta ? meta.content : null;
                }
                """,
            )

        except OzonAccessError:
            raise
        except Exception as exc:
            logger.warning("Ошибка карточки %s: %s", url, exc)

        return ProductResult(
            title=str(title),
            url=url,
            price=price,
            image_url=image,
            description=description,
            position=position,
        )

    async def run(
        self,
        query: str,
        limit: int,
        *,
        skip: int = 0,
        location: str | None = None,
        fetch_details: bool = False,
        batch_size: int = 4,
    ) -> list[ProductResult]:
        target_count = skip + limit
        if fetch_details and target_count <= batch_size * 2:
            raise ValueError(f"Требуется n > 2*m: n={target_count}, m={batch_size}")

        city = resolve_ozon_city(location)
        await self._apply_delivery_city(city)
        await self.search(query)
        listing_items = await self.collect_products(target_count)
        listing_items = listing_items[skip:target_count]
        if not listing_items:
            raise OzonAccessError("Товары в выдаче не найдены")

        if not fetch_details:
            return [
                ProductResult(
                    title=pick_ozon_product_title(i.get("title")) or i.get("title") or "Без названия",
                    url=i["url"],
                    price=i.get("price"),
                    original_price=i.get("originalPrice"),
                    image_url=i.get("image"),
                    description=None,
                    position=pos,
                )
                for pos, i in enumerate(listing_items, start=skip + 1)
            ]

        results: list[ProductResult] = []
        for pos, item in enumerate(listing_items, start=skip + 1):
            await asyncio.sleep(random.uniform(0.05, 0.1))
            if pos > 1 and (pos - 1) % batch_size == 0:
                pause = random.uniform(5, 10)
                logger.info("Пауза после %d товаров: %.1f с", batch_size, pause)
                await asyncio.sleep(pause)
            results.append(await self._parse_product_page(item["url"], item, pos))
        return results


def _log_cookie_session_hint(cookies_path: Path, count: int) -> None:
    try:
        raw = json.loads(cookies_path.read_text(encoding="utf-8"))
        items = raw.get("cookies", raw) if isinstance(raw, dict) else raw
        user_id = None
        if isinstance(items, list):
            for item in items:
                if item.get("name") == "__Secure-user-id":
                    user_id = item.get("value")
                    break
        if user_id in (None, "", "0"):
            logger.warning(
                "Ozon cookies (%s, %d items): __Secure-user-id=%r looks invalid — "
                "export fresh cookies from a logged-in browser session",
                cookies_path.name,
                count,
                user_id,
            )
    except Exception:
        pass


OzonSeleniumParser = OzonParser

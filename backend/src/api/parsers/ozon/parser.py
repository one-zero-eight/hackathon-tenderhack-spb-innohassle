from __future__ import annotations

import asyncio
import logging
import random
import re
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

from selenium_driverless.types.by import By
from selenium_driverless.types.webelement import NoSuchElementException
from selenium_driverless.webdriver import Chrome

from src.api.parsers.ozon.browser import create_driverless_driver
from src.api.parsers.ozon.exceptions import OzonAccessError
from src.api.parsers.ozon.models import ProductResult
from src.api.parsers.ozon.navigation import safe_get
from src.api.parsers.wait import wait_for_css

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
SEARCH_INPUT_CSS = (
    'input[name="text"], '
    'input[placeholder*="Искать"], '
    'input[placeholder*="искать"]'
)


class OzonSeleniumParser:
    def __init__(
        self,
        *,
        headless: bool = False,
        user_data_dir: str | None = None,
        cookies_file: str | Path | None = None,
        proxy: str | None = None,
        scroll_pause: tuple[float, float] = (2.0, 3.5),
        slow_mode: bool = False,
        page_load_timeout: int | None = None,
        element_wait_timeout: int = 45,
        page_load_retries: int = 4,
    ) -> None:
        self.headless = headless
        self.user_data_dir = user_data_dir
        self.cookies_file = cookies_file
        self.proxy = proxy
        self.slow_mode = slow_mode
        self.page_load_timeout = page_load_timeout
        self.element_wait_timeout = element_wait_timeout
        self.page_load_retries = page_load_retries
        self.scroll_pause = (
            (4.0, 6.0) if slow_mode else scroll_pause
        )
        self.driver: Chrome | None = None
        self.user_agent: str | None = None
        self.via_proxy: bool = False

    async def __aenter__(self) -> OzonSeleniumParser:
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def start(self) -> None:
        self.driver, self.user_agent, self.via_proxy = await create_driverless_driver(
            headless=self.headless,
            user_data_dir=self.user_data_dir,
            cookies_file=self.cookies_file,
            slow_mode=self.slow_mode,
            proxy=self.proxy,
            page_load_timeout=self.page_load_timeout,
            element_wait_timeout=self.element_wait_timeout,
            page_load_retries=self.page_load_retries,
        )

    async def close(self) -> None:
        if self.driver:
            await self.driver.quit()
            self.driver = None

    @property
    def _d(self) -> Chrome:
        if not self.driver:
            raise RuntimeError("Драйвер не запущен")
        return self.driver

    async def _sleep(self, min_sec: float, max_sec: float | None = None) -> None:
        await asyncio.sleep(random.uniform(min_sec, max_sec or min_sec))

    async def _is_blocked(self) -> bool:
        body = await self._d.execute_script(
            "return document.body ? document.body.innerText : ''",
        )
        url = (await self._d.current_url).lower()
        blob = f"{url} {(body or '').lower()}"
        return any(m in blob for m in BLOCKED_MARKERS)

    async def _goto(self, url: str) -> None:
        await safe_get(
            self._d,
            url,
            via_proxy=self.via_proxy,
            page_load_timeout=self.page_load_timeout,
            retries=self.page_load_retries,
        )
        if self.slow_mode or self.via_proxy:
            await self._sleep(4.0, 6.0)
        else:
            await self._sleep(1.0, 2.0)
        if await self._is_blocked():
            raise OzonAccessError(
                f"Ozon ограничил доступ: {url}. Попробуйте без --headless, --slow, меньший -n.",
                url=url,
            )

    async def _dismiss_overlays(self) -> None:
        for xpath in (
            "//button[contains(.,'OK')]",
            "//button[contains(.,'Понятно')]",
            "//button[contains(.,'Принять')]",
        ):
            try:
                btn = await self._d.find_element(By.XPATH, xpath, timeout=2)
                if await btn.is_visible():
                    await btn.click()
                    await self._sleep(0.3, 0.6)
            except Exception:
                continue

    async def search(self, query: str) -> None:
        logger.info("Поиск: %s", query)
        await self._goto(f"{OZON_HOME}search/?text={quote(query)}&from_global=true")
        await self._dismiss_overlays()
        try:
            await wait_for_css(
                self._d,
                "a[href*='/product/']",
                timeout=min(float(self.element_wait_timeout), 15.0),
            )
        except (TimeoutError, NoSuchElementException):
            await self._search_via_input(query)

    async def _search_via_input(self, query: str) -> None:
        await self._goto(OZON_HOME)
        await self._dismiss_overlays()
        try:
            field = await wait_for_css(
                self._d,
                SEARCH_INPUT_CSS,
                timeout=min(float(self.element_wait_timeout), 15.0),
            )
        except (TimeoutError, NoSuchElementException) as exc:
            raise OzonAccessError("Поле поиска не найдено") from exc
        await field.clear()
        await field.send_keys(query, click_on=False)
        await self._sleep(0.3, 0.7)
        await self._d.send_keys("\n")
        await self._sleep(2, 3)
        await wait_for_css(
            self._d,
            "a[href*='/product/']",
            timeout=min(float(self.element_wait_timeout), 15.0),
        )

    async def _scroll_step(self) -> None:
        await self._d.execute_script(
            """
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
            """
        )
        links = await self._d.find_elements(By.CSS_SELECTOR, "a[href*='/product/']")
        if links:
            try:
                await self._d.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    links[-1],
                )
            except Exception:
                pass
        await self._sleep(*self.scroll_pause)

    def _normalize_url(self, href: str) -> str | None:
        if "/product/" not in href:
            return None
        full = urljoin(OZON_HOME, href)
        parsed = urlparse(full)
        if "ozon.ru" not in parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    async def _extract_from_listing(self) -> list[dict]:
        script = """
        const pickImage = (img) => {
          if (!img) return null;
          const src = img.currentSrc || img.src || img.getAttribute('data-src');
          return src && src.startsWith('http') && !src.startsWith('data:') ? src : null;
        };
        const out = [];
        const seen = new Set();
        for (const a of document.querySelectorAll('a[href*="/product/"]')) {
          const href = a.href || a.getAttribute('href');
          if (!href || seen.has(href)) continue;
          seen.add(href);
          const tile = a.closest('[data-index]') || a.closest('.tile-root') || a;
          const img = tile.querySelector('img');
          const priceEl = tile.querySelector('[class*="price"]');
          out.push({
            href,
            title: (a.getAttribute('title') || a.innerText || '').trim().slice(0, 500),
            price: priceEl ? priceEl.innerText.trim().slice(0, 80) : null,
            image: pickImage(img),
          });
        }
        return out;
        """
        try:
            result = await self._d.execute_script(script)
            return result or []
        except Exception:
            return []

    async def collect_products(self, limit: int) -> list[dict]:
        ordered: list[dict] = []
        seen: set[str] = set()
        stale = 0
        prev_total = 0
        max_rounds = max(30, limit * 2)

        logger.info("Прокрутка выдачи для %d товаров...", limit)

        for _rnd in range(max_rounds):
            if await self._is_blocked():
                if ordered:
                    logger.warning("Блокировка после %d товаров", len(ordered))
                    break
                raise OzonAccessError("Блокировка при загрузке выдачи")

            for item in await self._extract_from_listing():
                url = self._normalize_url(item.get("href", ""))
                if not url or url in seen:
                    continue
                seen.add(url)
                ordered.append({**item, "url": url})
                if len(ordered) >= limit:
                    return ordered[:limit]

            if len(ordered) == prev_total:
                stale += 1
            else:
                stale = 0
            prev_total = len(ordered)

            if stale >= 4:
                await self._d.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                await self._sleep(2, 3)
                stale = 0
                continue

            await self._scroll_step()

        return ordered[:limit]

    async def _parse_product_page(self, url: str, listing: dict, position: int) -> ProductResult:
        logger.info("[%d] Карточка: %s", position, url)
        title = listing.get("title") or "Без названия"
        price = listing.get("price")
        image = listing.get("image")
        description = None

        try:
            await self._goto(url)
            try:
                h1 = await self._d.find_element(By.CSS_SELECTOR, "h1", timeout=self.element_wait_timeout)
                title = ((await h1.text) or title).strip()
            except (TimeoutError, NoSuchElementException):
                pass

            for sel in ("[data-widget='webPrice']", "span[class*='price']"):
                try:
                    el = await self._d.find_element(By.CSS_SELECTOR, sel, timeout=5)
                    text = await el.text
                    if text and re.search(r"\d", text):
                        price = re.sub(r"\s+", " ", text.strip())
                        break
                except Exception:
                    continue

            for sel in (
                "[data-widget='webDescription']",
                "meta[property='og:image']",
                "img[src*='ir.ozone.ru']",
            ):
                try:
                    el = await self._d.find_element(By.CSS_SELECTOR, sel, timeout=5)
                    if sel.startswith("meta"):
                        image = (await el.get_attribute("content")) or image
                    elif "Description" in sel:
                        text = await el.text
                        if len(text) > 30:
                            description = text.strip()
                    else:
                        image = (await el.get_attribute("src")) or image
                except Exception:
                    continue

            if not description:
                try:
                    meta = await self._d.find_element(By.CSS_SELECTOR, 'meta[name="description"]', timeout=5)
                    description = await meta.get_attribute("content")
                except Exception:
                    pass

        except OzonAccessError:
            raise
        except Exception as exc:
            logger.warning("Ошибка карточки %s: %s", url, exc)

        return ProductResult(
            title=title,
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
        fetch_details: bool = False,
        batch_size: int = 4,
    ) -> list[ProductResult]:
        if limit <= batch_size * 2:
            raise ValueError(f"Требуется n > 2*m: n={limit}, m={batch_size}")

        await self.search(query)
        listing_items = await self.collect_products(limit)
        if not listing_items:
            raise OzonAccessError("Товары в выдаче не найдены")

        if not fetch_details:
            return [
                ProductResult(
                    title=i.get("title") or "Без названия",
                    url=i["url"],
                    price=i.get("price"),
                    image_url=i.get("image"),
                    description=None,
                    position=pos,
                )
                for pos, i in enumerate(listing_items, start=1)
            ]

        results: list[ProductResult] = []
        for pos, item in enumerate(listing_items, start=1):
            await asyncio.sleep(random.uniform(0.05, 0.1))
            if pos > 1 and (pos - 1) % batch_size == 0:
                pause = random.uniform(5, 10)
                logger.info("Пауза после %d товаров: %.1f с", batch_size, pause)
                await asyncio.sleep(pause)
            results.append(await self._parse_product_page(item["url"], item, pos))
        return results

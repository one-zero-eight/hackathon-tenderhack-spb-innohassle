from __future__ import annotations

import logging
import random
import re
import time
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver import Chrome
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.api.parsers.ozon.browser import create_stealth_driver
from src.api.parsers.ozon.exceptions import OzonAccessError
from src.api.parsers.ozon.models import ProductResult
from src.api.parsers.ozon.navigation import safe_get

logger = logging.getLogger(__name__)

OZON_HOME = "https://www.ozon.ru/"
PRODUCT_HREF_RE = re.compile(
    r'https?://(?:www\.)?ozon\.ru/product/[^\s"\'<>]+|/product/[^\s"\'<>]+',
    re.I,
)
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

    def __enter__(self) -> OzonSeleniumParser:
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def start(self) -> None:
        self.driver, self.user_agent, self.via_proxy = create_stealth_driver(
            headless=self.headless,
            user_data_dir=self.user_data_dir,
            cookies_file=self.cookies_file,
            slow_mode=self.slow_mode,
            proxy=self.proxy,
            page_load_timeout=self.page_load_timeout,
            element_wait_timeout=self.element_wait_timeout,
            page_load_retries=self.page_load_retries,
        )

    def close(self) -> None:
        if self.driver:
            self.driver.quit()
            self.driver = None

    @property
    def _d(self) -> Chrome:
        if not self.driver:
            raise RuntimeError("Драйвер не запущен")
        return self.driver

    def _sleep(self, min_sec: float, max_sec: float | None = None) -> None:
        time.sleep(random.uniform(min_sec, max_sec or min_sec))

    def _is_blocked(self) -> bool:
        body = self._d.find_element(By.TAG_NAME, "body").text.lower()
        url = self._d.current_url.lower()
        blob = f"{url} {body}"
        return any(m in blob for m in BLOCKED_MARKERS)

    def _goto(self, url: str) -> None:
        safe_get(
            self._d,
            url,
            via_proxy=self.via_proxy,
            page_load_timeout=self.page_load_timeout,
            retries=self.page_load_retries,
        )
        self._sleep(4.0, 6.0 if self.via_proxy else 4.0)
        if self._is_blocked():
            raise OzonAccessError(
                f"Ozon ограничил доступ: {url}. Попробуйте без --headless, --slow, меньший -n.",
                url=url,
            )

    def _dismiss_overlays(self) -> None:
        for xpath in (
            "//button[contains(.,'OK')]",
            "//button[contains(.,'Понятно')]",
            "//button[contains(.,'Принять')]",
        ):
            try:
                btn = self._d.find_element(By.XPATH, xpath)
                if btn.is_displayed():
                    btn.click()
                    self._sleep(0.3, 0.6)
            except Exception:
                continue

    def search(self, query: str) -> None:
        logger.info("Поиск: %s", query)
        self._goto(f"{OZON_HOME}search/?text={quote(query)}&from_global=true")
        self._dismiss_overlays()
        try:
            WebDriverWait(self._d, self.element_wait_timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/product/']")),
            )
        except TimeoutException:
            self._search_via_input(query)

    def _search_via_input(self, query: str) -> None:
        self._goto(OZON_HOME)
        self._dismiss_overlays()
        try:
            field = WebDriverWait(self._d, self.element_wait_timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SEARCH_INPUT_CSS)),
            )
        except TimeoutException as exc:
            raise OzonAccessError("Поле поиска не найдено") from exc
        field.clear()
        field.send_keys(query)
        self._sleep(0.3, 0.7)
        field.send_keys(Keys.ENTER)
        self._sleep(2, 3)
        WebDriverWait(self._d, self.element_wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/product/']")),
        )

    def _scroll_step(self) -> None:
        self._d.execute_script(
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
        links = self._d.find_elements(By.CSS_SELECTOR, "a[href*='/product/']")
        if links:
            try:
                self._d.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    links[-1],
                )
            except Exception:
                pass
        self._sleep(*self.scroll_pause)

    def _normalize_url(self, href: str) -> str | None:
        if "/product/" not in href:
            return None
        full = urljoin(OZON_HOME, href)
        parsed = urlparse(full)
        if "ozon.ru" not in parsed.netloc:
            return None
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    def _extract_from_listing(self) -> list[dict]:
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
            return self._d.execute_script(script) or []
        except WebDriverException:
            return []

    def collect_products(self, limit: int) -> list[dict]:
        ordered: list[dict] = []
        seen: set[str] = set()
        stale = 0
        prev_total = 0
        max_rounds = max(30, limit * 2)

        logger.info("Прокрутка выдачи для %d товаров...", limit)

        for rnd in range(max_rounds):
            if self._is_blocked():
                if ordered:
                    logger.warning("Блокировка после %d товаров", len(ordered))
                    break
                raise OzonAccessError("Блокировка при загрузке выдачи")

            for item in self._extract_from_listing():
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
                self._d.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                self._sleep(2, 3)
                stale = 0
                continue

            self._scroll_step()

        return ordered[:limit]

    def _parse_product_page(self, url: str, listing: dict, position: int) -> ProductResult:
        logger.info("[%d] Карточка: %s", position, url)
        title = listing.get("title") or "Без названия"
        price = listing.get("price")
        image = listing.get("image")
        description = None

        try:
            self._goto(url)
            try:
                h1 = WebDriverWait(self._d, self.element_wait_timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "h1")),
                )
                title = (h1.text or title).strip()
            except TimeoutException:
                pass

            for sel in ("[data-widget='webPrice']", "span[class*='price']"):
                try:
                    el = self._d.find_element(By.CSS_SELECTOR, sel)
                    if el.text and re.search(r"\d", el.text):
                        price = re.sub(r"\s+", " ", el.text.strip())
                        break
                except Exception:
                    continue

            for sel in (
                "[data-widget='webDescription']",
                "meta[property='og:image']",
                "img[src*='ir.ozone.ru']",
            ):
                try:
                    el = self._d.find_element(By.CSS_SELECTOR, sel)
                    if sel.startswith("meta"):
                        image = el.get_attribute("content") or image
                    elif "Description" in sel:
                        if len(el.text) > 30:
                            description = el.text.strip()
                    else:
                        image = el.get_attribute("src") or image
                except Exception:
                    continue

            if not description:
                try:
                    meta = self._d.find_element(By.CSS_SELECTOR, 'meta[name="description"]')
                    description = meta.get_attribute("content")
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

    def run(
        self,
        query: str,
        limit: int,
        *,
        fetch_details: bool = False,
        batch_size: int = 4,
    ) -> list[ProductResult]:
        if limit <= batch_size * 2:
            raise ValueError(f"Требуется n > 2*m: n={limit}, m={batch_size}")

        self.search(query)
        listing_items = self.collect_products(limit)
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
            time.sleep(random.uniform(0.05, 0.1))
            if pos > 1 and (pos - 1) % batch_size == 0:
                pause = random.uniform(5, 10)
                logger.info("Пауза после %d товаров: %.1f с", batch_size, pause)
                time.sleep(pause)
            results.append(self._parse_product_page(item["url"], item, pos))
        return results

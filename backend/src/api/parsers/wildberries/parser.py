from __future__ import annotations

import asyncio
import json
import logging
import re
from urllib.parse import quote_plus

from selenium_driverless.types.by import By
from selenium_driverless.types.webelement import NoSuchElementException, WebElement
from selenium_driverless.webdriver import Chrome

from src.api.parsers.wait import wait_for_css
from src.api.parsers.wildberries.browser import create_driverless_driver
from src.api.parsers.wildberries.exceptions import WildberriesAccessError
from src.api.parsers.wildberries.navigation import safe_get

logger = logging.getLogger(__name__)

WB_SEARCH = "https://www.wildberries.ru/catalog/0/search.aspx?search="
PRODUCT_CARD_SELECTOR = "article, .product-card, [data-nm-id]"
BLOCKED_MARKERS = (
    "почти готов",
    "captcha",
    "доступ ограничен",
    "подтвердите",
    "не робот",
)
MAX_SCROLL_ATTEMPTS = 30
SCROLL_PAUSE_SECONDS = 1.0


class WildberriesSeleniumParser:
    def __init__(
        self,
        *,
        headless: bool = True,
        page_load_timeout: int | None = None,
        element_wait_timeout: int = 45,
        page_load_retries: int = 3,
    ) -> None:
        self.headless = headless
        self.page_load_timeout = page_load_timeout
        self.element_wait_timeout = element_wait_timeout
        self.page_load_retries = page_load_retries
        self.driver: Chrome | None = None
        self.user_agent: str | None = None

    async def __aenter__(self) -> WildberriesSeleniumParser:
        await self.start()
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def start(self) -> None:
        self.driver, self.user_agent = await create_driverless_driver(headless=self.headless)

    async def close(self) -> None:
        if self.driver:
            await self.driver.quit()
            self.driver = None

    @property
    def _d(self) -> Chrome:
        if not self.driver:
            raise RuntimeError("Драйвер не запущен")
        return self.driver

    async def _is_blocked(self) -> bool:
        title = (await self._d.title).lower()
        body = await self._d.execute_script(
            "return document.body ? document.body.innerText : ''",
        )
        blob = f"{title} {(body or '').lower()}"
        return any(marker in blob for marker in BLOCKED_MARKERS)

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

    async def _open_search_page(self, keyword: str, *, dest: int) -> None:
        search_url = f"{WB_SEARCH}{quote_plus(keyword)}&dest={dest}"
        last_error: Exception | None = None
        cards_timeout = min(float(self.element_wait_timeout), 15.0)

        for attempt in range(1, self.page_load_retries + 1):
            try:
                await safe_get(
                    self._d,
                    search_url,
                    page_load_timeout=self.page_load_timeout,
                    retries=1,
                )
                await self._apply_dest_cookies(dest)
                await safe_get(
                    self._d,
                    search_url,
                    page_load_timeout=self.page_load_timeout,
                    retries=1,
                )
                await asyncio.sleep(1)

                cards = await self._d.find_elements(
                    By.CSS_SELECTOR,
                    PRODUCT_CARD_SELECTOR,
                    timeout=3,
                )
                if await self._is_blocked() or not cards:
                    title = await self._d.title
                    raise WildberriesAccessError(
                        f"anti-bot or empty page (title={title!r}, cards={len(cards)})",
                        url=search_url,
                    )

                await wait_for_css(
                    self._d,
                    PRODUCT_CARD_SELECTOR,
                    timeout=cards_timeout,
                )
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Wildberries page load attempt %d/%d failed: %s",
                    attempt,
                    self.page_load_retries,
                    exc,
                )
                if attempt < self.page_load_retries:
                    await asyncio.sleep(1)

        raise WildberriesAccessError(
            f"Failed to open Wildberries search page: {last_error}",
            url=search_url,
        ) from last_error

    async def _load_product_cards(self, target_count: int) -> list[WebElement]:
        previous_count = 0
        stable_attempts = 0

        for _ in range(MAX_SCROLL_ATTEMPTS):
            cards = await self._d.find_elements(
                By.CSS_SELECTOR,
                PRODUCT_CARD_SELECTOR,
                timeout=10,
            )
            if len(cards) >= target_count:
                return cards

            if len(cards) == previous_count:
                stable_attempts += 1
            else:
                stable_attempts = 0

            if stable_attempts >= 3:
                return cards

            previous_count = len(cards)
            await self._d.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(SCROLL_PAUSE_SECONDS)

        return await self._d.find_elements(
            By.CSS_SELECTOR,
            PRODUCT_CARD_SELECTOR,
            timeout=10,
        )

    async def _parse_product_card(self, card: WebElement) -> dict:
        price_text = await self._find_text(
            card,
            ".price__lower-price, .price__wrap, .product-card__price, "
            "ins[class*='price'], span[class*='price']",
        )
        original_price_text = await self._find_text(
            card,
            "del, .price__wrap del, .product-card__price-old, span[class*='price-old']",
        )
        link = await self._find_attribute(card, "a.product-card__link, a[href*='/catalog/']", "href")
        image_url = await self._find_attribute(card, "img", "src") or await self._find_attribute(
            card,
            "img",
            "data-src",
        )

        return {
            "name": _clean_name(await self._find_text(card, ".product-card__name, .goods-name")),
            "brand": _clean_text(await self._find_text(card, ".product-card__brand, .brand-name")),
            "sale_price": _parse_price(price_text),
            "original_price": _parse_price(original_price_text),
            "url": link,
            "image_url": image_url,
            "source": "Wildberries",
        }

    async def _find_text(self, card: WebElement, selector: str) -> str | None:
        try:
            element = await card.find_element(By.CSS_SELECTOR, selector, timeout=2)
        except (NoSuchElementException, TimeoutError):
            return None
        return _clean_text(await element.text)

    async def _find_attribute(self, card: WebElement, selector: str, attribute: str) -> str | None:
        try:
            element = await card.find_element(By.CSS_SELECTOR, selector, timeout=2)
        except (TimeoutError, NoSuchElementException):
            return None
        return _clean_text(await element.get_attribute(attribute))

    async def run(
        self,
        keyword: str,
        limit: int,
        *,
        skip: int = 0,
        dest: int = -1257786,
    ) -> list[dict]:
        logger.info("Wildberries search: %r (dest=%d)", keyword, dest)
        await self._open_search_page(keyword, dest=dest)

        cards = await self._load_product_cards(skip + limit)
        products: list[dict] = []
        skipped = 0

        for card in cards:
            product = await self._parse_product_card(card)
            if product.get("sale_price") is None:
                continue
            if skipped < skip:
                skipped += 1
                continue
            products.append(product)
            if len(products) >= limit:
                break

        logger.info(
            "Wildberries parse done for %r (limit=%d): %d items",
            keyword,
            limit,
            len(products),
        )
        return products


def _parse_price(value: str | None) -> int | None:
    if not value:
        return None
    price_match = re.search(r"(\d[\d\s\u00a0]*)\s*₽", value)
    clean_price = "".join(filter(str.isdigit, price_match.group(1) if price_match else value))
    return int(clean_price) if clean_price else None


def _clean_name(value: str | None) -> str | None:
    if not value:
        return None
    return value.removeprefix("/").strip() or None


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    return " ".join(value.split()) or None

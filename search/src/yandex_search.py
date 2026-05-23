from __future__ import annotations

import _bootstrap  # noqa: F401

import asyncio
import json
import logging
import os
import random
import sys
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.async_api import BrowserContext, Page

from cloak_browser import (
    CloakSessionConfig,
    close_cloak_session,
    new_pool_profile_dir,
    open_cloak_session,
)
from config import yandex_search_settings
from notify import notify_captcha
from proxy_bridge import bridge_manager
from query_rewrite import rewrite_query

logger = logging.getLogger(__name__)

YA_RU_URL = "https://ya.ru/"
COOKIES_PATH = Path(__file__).resolve().parent.parent / "yandex_cookies.json"
RESPONSE_JSON_PATH = Path(__file__).resolve().parent.parent / "response.json"
SEARCH_INPUT_SELECTOR = "textarea#text"
PAGER_NEXT_SELECTORS = (
    ".Pager a.Pager-Item_type_next",
    ".Pager-ListItem_type_next a",
    ".Pager a[aria-label='Следующая страница']",
)
MAX_PAGER_CLICKS = 1


def _resolve_headless() -> bool:
    env = os.getenv("CLOAK_HEADLESS") or os.getenv("PLAYWRIGHT_HEADLESS")
    if env is not None:
        return env.lower() in {"1", "true", "yes"}
    return yandex_search_settings.headless


MACBOOK = os.getenv("MACBOOK", "false").lower() in {"1", "true", "yes"}
CAPTCHA_WAIT_TIMEOUT_MS = int(os.getenv("CAPTCHA_WAIT_TIMEOUT_MS", "1800000"))
HEADLESS_CAPTCHA_WAIT_MS = int(os.getenv("HEADLESS_CAPTCHA_WAIT_MS", "120000"))
SEARCH_RESULTS_SELECTOR = "ul#search-result li.serp-item"

_captcha_wait_callback: Callable[[], Awaitable[None]] | None = None

_COOKIE_STRIP_KEYS = (
    "expirationDate",
    "sameSite",
    "partitionKey",
    "storeId",
    "hostOnly",
    "firstPartyDomain",
    "session",
)

next_request_time: float = 0.0
_session: YandexBrowserSession | None = None

speed_factor = 0.5

PAGER_TIME_SLEEP_SECONDS = (10 * speed_factor, 20 * speed_factor)
SCROLL_TARGET_DEPTH_FRACTION = (0.55 * speed_factor, 0.95 * speed_factor)
SCROLL_BACK_UP_CHANCE = 0.12 * speed_factor
SCROLL_BACK_UP_VIEWPORT_FRACTION = (0.05 * speed_factor, 0.2 * speed_factor)
SCROLL_DOWN_VIEWPORT_FRACTION = (0.12 * speed_factor, 0.5 * speed_factor)
SCROLL_STEP_PAUSE_SECONDS = (0.08 * speed_factor, 0.35 * speed_factor)
SCROLL_LONG_PAUSE_CHANCE = 0.2 * speed_factor
SCROLL_LONG_PAUSE_SECONDS = (0.25 * speed_factor, 0.85 * speed_factor)

def load_yandex_cookies(path: Path = COOKIES_PATH) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"Yandex cookies file not found: {path}. "
            "Copy yandex_cookies.example.json to yandex_cookies.json and fill in your cookies."
        )

    with path.open(encoding="utf-8") as file:
        cookies = json.load(file)

    for cookie in cookies:
        for key in _COOKIE_STRIP_KEYS:
            cookie.pop(key, None)

    return cookies


def _proxy_log_label(proxy_url: str | None) -> str:
    if not proxy_url:
        return "none"
    parsed = urlparse(proxy_url if "://" in proxy_url else f"socks5://{proxy_url}")
    host = parsed.hostname or "?"
    port = f":{parsed.port}" if parsed.port else ""
    if parsed.username:
        return f"{parsed.scheme}://***@{host}{port}"
    return f"{parsed.scheme}://{host}{port}"


class YandexCaptchaError(RuntimeError):
    pass


def set_captcha_wait_callback(callback: Callable[[], Awaitable[None]] | None) -> None:
    global _captcha_wait_callback
    _captcha_wait_callback = callback


async def _is_captcha_page(page: Page) -> bool:
    url = page.url.lower()
    if "showcaptcha" in url or "checkcaptcha" in url:
        return True
    if await page.locator('[data-testid="checkbox-captcha"]').count():
        return True
    if await page.locator('form[action*="checkcaptcha"]').count():
        return True
    heading = page.locator("h1").filter(has_text="робот")
    return bool(await heading.count())


def _captcha_wait_timeout_ms() -> int:
    if MACBOOK and sys.platform == "darwin" and not _resolve_headless():
        return CAPTCHA_WAIT_TIMEOUT_MS
    return HEADLESS_CAPTCHA_WAIT_MS


_HEADLESS_CAPTCHA_HINT = (
    "Yandex showed a captcha but CloakBrowser runs headless. "
    "Set yandex_search_settings.headless: false in settings.yaml "
    "(or MACBOOK=true and CLOAK_HEADLESS=false in .env), solve captcha in the "
    "browser window, and refresh yandex_cookies.json from the same SOCKS5 proxy."
)


async def _wait_until_captcha_cleared(page: Page) -> None:
    if not await _is_captcha_page(page):
        return

    notify_captcha()
    if _resolve_headless():
        raise YandexCaptchaError(_HEADLESS_CAPTCHA_HINT)

    if _captcha_wait_callback is not None:
        await _captcha_wait_callback()

    deadline = time.monotonic() + _captcha_wait_timeout_ms() / 1000
    while time.monotonic() < deadline:
        if not await _is_captcha_page(page):
            return
        await asyncio.sleep(0.5)

    raise YandexCaptchaError(
        "Timed out waiting for captcha to be solved in the browser window",
    )


async def _wait_for_search_results(page: Page, *, after_captcha: bool) -> None:
    timeout_ms = _captcha_wait_timeout_ms() if after_captcha else 150_000
    try:
        await page.wait_for_selector(SEARCH_RESULTS_SELECTOR, timeout=timeout_ms)
    except Exception as error:
        if after_captcha:
            msg = "Timed out waiting for Yandex SERP after captcha"
        else:
            msg = "Timed out waiting for Yandex search results"
        raise YandexCaptchaError(msg) from error


class YandexBrowserSession:
    def __init__(
        self,
        cookies_path: Path = COOKIES_PATH,
        proxy: str | None = None,
    ) -> None:
        self._cookies_path = cookies_path
        self._proxy = proxy if proxy is not None else yandex_search_settings.resolve_proxy()
        self._context: BrowserContext | None = None
        self._bridge_upstream: str | None = None
        self._profile_dir = new_pool_profile_dir("yandex")
        self._home_page: Page | None = None

    async def start(self) -> None:
        if self._context is not None:
            return

        cookies = load_yandex_cookies(self._cookies_path)
        label = _proxy_log_label(self._proxy)
        logger.info("Yandex search CloakBrowser starting (proxy=%s)", label)
        config = CloakSessionConfig(
            headless=_resolve_headless(),
            proxy=self._proxy,
            geoip=yandex_search_settings.geoip and bool(self._proxy),
            humanize=yandex_search_settings.humanize,
            user_data_dir=self._profile_dir,
        )
        self._context, self._home_page, self._bridge_upstream = await open_cloak_session(config)
        await self._context.add_cookies(cookies)
        await self._home_page.goto(YA_RU_URL, wait_until="domcontentloaded", timeout=30_000)
        logger.info("Yandex search CloakBrowser ready (proxy=%s)", label)

    async def stop(self) -> None:
        self._home_page = None
        await close_cloak_session(
            self._context,
            bridge_upstream=self._bridge_upstream,
        )
        self._context = None
        self._bridge_upstream = None

    async def _open_search_tab(self) -> Page:
        if self._context is None:
            raise RuntimeError("Browser session is not started")
        return await self._context.new_page()

    async def search(self, query: str, region: str = "санкт-петербург") -> AsyncGenerator[list[dict], None]:
        if self._context is None:
            raise RuntimeError("Browser session is not started")

        rewritten_query = rewrite_query(query, region)
        page = self._home_page or await self._open_search_tab()
        own_tab = page is not self._home_page
        try:
            serp_index = 0
            started = time.perf_counter()
            await _submit_search(page, rewritten_query)
            results = _parse_results(await _current_soup(page))
            serp_index += 1
            logger.info(
                "yandex serp page %d: %.2fs, %d items (query=%r)",
                serp_index,
                time.perf_counter() - started,
                len(results),
                rewritten_query,
            )
            yield results

            for _ in range(MAX_PAGER_CLICKS):
                try:
                    pager_started = time.perf_counter()
                    if not await _click_next_page(page):
                        break
                except YandexCaptchaError as error:
                    logger.warning("%s", error)
                    break
                results = _parse_results(await _current_soup(page))
                serp_index += 1
                logger.info(
                    "yandex serp page %d: %.2fs, %d items",
                    serp_index,
                    time.perf_counter() - pager_started,
                    len(results),
                )
                yield results
        finally:
            if own_tab:
                await page.close()


async def init_browser_session(
    cookies_path: Path = COOKIES_PATH,
    proxy: str | None = None,
) -> YandexBrowserSession:
    global _session
    if _session is None:
        _session = YandexBrowserSession(cookies_path=cookies_path, proxy=proxy)
        await _session.start()
    return _session


async def close_browser_session() -> None:
    global _session
    if _session is not None:
        await _session.stop()
        _session = None
    await bridge_manager.shutdown_all()


def get_browser_session() -> YandexBrowserSession:
    if _session is None:
        raise RuntimeError("Browser session is not started")
    return _session


async def _respect_rate_limit() -> None:
    global next_request_time
    now = time.monotonic()
    if now < next_request_time:
        await asyncio.sleep(next_request_time - now)
        await asyncio.sleep(random.uniform(0.1, 1))


async def _wait_for_results(page: Page, *, after_captcha: bool) -> None:
    await _wait_for_search_results(page, after_captcha=after_captcha)
    await _scroll_page_chaotically(page)
    global next_request_time
    next_request_time = time.monotonic() + random.uniform(*PAGER_TIME_SLEEP_SECONDS)


async def _current_soup(page: Page) -> BeautifulSoup:
    return BeautifulSoup(await page.content(), "html.parser")


async def _human_pause(min_seconds: float, max_seconds: float) -> None:
    await asyncio.sleep(random.uniform(min_seconds, max_seconds))


def _query_typing_chunks(query: str) -> list[str]:
    words = query.split()
    if not words:
        return []

    chunks: list[str] = []
    index = 0
    while index < len(words):
        take = random.randint(1, min(2, len(words) - index))
        chunks.append(" ".join(words[index:index + take]))
        index += take
    return chunks


async def _type_query_naturally(search_input, query: str) -> None:
    chunks = _query_typing_chunks(query)
    if not chunks:
        return

    for index, chunk in enumerate(chunks):
        if index > 0:
            await search_input.press_sequentially(" ", delay=random.randint(40, 110))
            await _human_pause(0.05, 0.25)
        await search_input.press_sequentially(
            chunk,
            delay=random.randint(60, 180),
        )
        if index < len(chunks) - 1:
            await _human_pause(0.15, 0.55)

    await _human_pause(1, 2)


async def _scroll_page_chaotically(page: Page) -> None:
    metrics = await page.evaluate(
        """() => ({
            viewport: window.innerHeight,
            height: Math.max(
                document.body.scrollHeight,
                document.documentElement.scrollHeight,
            ),
        })"""
    )
    viewport_height = metrics["viewport"]
    scroll_height = metrics["height"]
    if scroll_height <= viewport_height:
        return

    max_position = scroll_height - viewport_height
    target_position = max_position * random.uniform(*SCROLL_TARGET_DEPTH_FRACTION)
    position = 0.0

    while position < target_position:
        if random.random() < SCROLL_BACK_UP_CHANCE:
            step = -random.uniform(
                viewport_height * SCROLL_BACK_UP_VIEWPORT_FRACTION[0],
                viewport_height * SCROLL_BACK_UP_VIEWPORT_FRACTION[1],
            )
        else:
            step = random.uniform(
                viewport_height * SCROLL_DOWN_VIEWPORT_FRACTION[0],
                viewport_height * SCROLL_DOWN_VIEWPORT_FRACTION[1],
            )

        position = max(0.0, min(position + step, max_position))
        await page.evaluate(
            "(y) => window.scrollTo({ top: y, behavior: 'instant' })",
            position,
        )
        await _human_pause(*SCROLL_STEP_PAUSE_SECONDS)

        if random.random() < SCROLL_LONG_PAUSE_CHANCE:
            await _human_pause(*SCROLL_LONG_PAUSE_SECONDS)


async def _submit_search(page: Page, query: str) -> None:
    await _respect_rate_limit()
    if YA_RU_URL not in page.url:
        await page.goto(YA_RU_URL, wait_until="domcontentloaded", timeout=30_000)

    await _wait_until_captcha_cleared(page)

    search_input = page.locator(SEARCH_INPUT_SELECTOR)
    await search_input.wait_for(state="visible", timeout=30_000)
    await search_input.click()
    await _human_pause(0.15, 0.45)
    await _type_query_naturally(search_input, query)
    await search_input.press("Enter")
    await _human_pause(0.5, 1.2)

    await _wait_until_captcha_cleared(page)
    await _wait_for_results(page, after_captcha=False)


async def _find_next_page_link(page: Page):
    for selector in PAGER_NEXT_SELECTORS:
        link = page.locator(selector)
        if await link.count() > 0:
            return link.first
    return None


async def _click_next_page(page: Page) -> bool:
    next_link = await _find_next_page_link(page)
    if next_link is None:
        return False

    await _respect_rate_limit()
    await next_link.click()

    await _wait_until_captcha_cleared(page)
    await _wait_for_results(page, after_captcha=False)
    return True


def _parse_results(soup: BeautifulSoup) -> list[dict]:
    results: list[dict] = []
    ul = soup.find("ul", id="search-result")
    if not ul:
        return results

    for li in ul.select("li.serp-item"):
        if li.select("div[class*='AdvLabel']"):
            continue

        title = li.select_one(".OrganicTitle-LinkText")
        url = li.select_one("a.OrganicTitle-Link")
        hostname = urlparse(url.get("href")).hostname if url else None
        href = url.get("href") if url else None

        rating_el = li.select_one(".OrganicUgcReviews-RatingContainer .RatingOneStar .Line-AddonContent")
        rating = rating_el.get_text(strip=True) if rating_el else None

        reviews_el = li.select_one(".OrganicUgcReviews-RatingContainer .EReviews")
        reviews = reviews_el.get_text(strip=True).removesuffix("на магазин") if reviews_el else None

        delivery_container_el = li.select_one(".ShopInfo-DeliveryBnplContainer .EDeliveryGroup-Item")
        delivery_container = delivery_container_el.get_text(strip=True) if delivery_container_el else None

        price_el = li.select_one(".EPriceGroup .EPriceGroup-Price .EPrice-Content")
        price = price_el.get("title") if price_el else None

        thumbnail_el = li.select_one(".EThumb img")
        thumbnail = thumbnail_el.get("src") if thumbnail_el else None

        if title and hostname:
            results.append({
                "title": title.get_text(strip=True),
                "hostname": hostname,
                "href": href,
                "rating": rating,
                "reviews": reviews,
                "delivery": delivery_container,
                "price": price,
                "thumbnail": thumbnail,
            })

    return results


def _hostname_shop_fields(products: list[dict]) -> tuple[str | None, str | None]:
    rating = None
    reviews = None
    for product in products:
        if rating is None:
            rating = product.get("rating")
        if reviews is None:
            reviews = product.get("reviews")
        if rating is not None and reviews is not None:
            break
    return rating, reviews


def _hostname_group(hostname: str, products: list[dict]) -> dict:
    rating, reviews = _hostname_shop_fields(products)
    group: dict = {"hostname": hostname, "products": products}
    if rating is not None:
        group["rating"] = rating
    if reviews is not None:
        group["reviews"] = reviews
    return group


def _group_by_hostname(products: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for product in products:
        hostname = product.get("hostname")
        if not hostname:
            continue
        grouped.setdefault(hostname, []).append(product)

    return [
        _hostname_group(hostname, items)
        for hostname, items in sorted(grouped.items())
    ]


def _summarize_results(results: list[dict]) -> tuple[int, int, int, int]:
    hostnames = len(results)
    products = 0
    extracted = 0
    non_extracted = 0

    for group in results:
        for product in group.get("products", []):
            products += 1
            if product.get("extracted"):
                extracted += 1
            else:
                non_extracted += 1

    return hostnames, products, extracted, non_extracted


def _print_event_summary(event: dict) -> None:
    event_type = event.get("type")

    if event_type == "meta":
        print(f"meta: query={event.get('query')!r}")
        return

    if event_type == "page":
        hostnames, products, extracted, non_extracted = _summarize_results(event.get("results", []))
        print(
            f"page: "
            f"hostnames={hostnames} "
            f"products={products} "
            f"extracted={extracted} "
            f"non_extracted={non_extracted}"
        )
        return

    if event_type == "done":
        print("done")
        return

    print(f"{event_type}: {event}")


def _write_response(event: dict) -> None:
    with RESPONSE_JSON_PATH.open("w", encoding="utf-8") as file:
        json.dump(event, file, ensure_ascii=False, indent=2)


def _log_event(event: dict) -> None:
    _write_response(event)


async def search_yandex(query: str, region: str = "санкт-петербург") -> AsyncGenerator[list[dict], None]:
    rewritten_query = rewrite_query(query, region)
    _log_event({
        "type": "meta",
        "query": query,
        "region": region,
        "rewritten_query": rewritten_query,
    })

    session = get_browser_session()
    async for results in session.search(query, region):
        _log_event({
            "type": "page",
            "results": _group_by_hostname(results),
        })
        yield results

    _log_event({"type": "done"})


async def _main() -> None:
    await init_browser_session()
    try:
        for i in range(4, 17):
            query = f"айфон {i}"
            try:
                print(f"searching {query}")
                async for results in search_yandex(query, region="санкт-петербург"):
                    _print_event_summary({
                        "type": "page",
                        "results": _group_by_hostname(results),
                    })
                    print(f"found {len(results)} results...")
                    for result in results:
                        print(result)
                        print("-" * 100)
            except YandexCaptchaError as error:
                print(error)
    finally:
        await close_browser_session()


if __name__ == "__main__":
    asyncio.run(_main())

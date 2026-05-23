from __future__ import annotations

import asyncio
import json
import os
import random
import sys
import time
from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence
from pathlib import Path
from urllib.parse import urlencode, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from notify import notify_captcha
from query_rewrite import rewrite_query

YANDEX_SEARCH_URL = "https://yandex.ru/search/"
COOKIES_PATH = Path(__file__).resolve().parent.parent / "yandex_cookies.json"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

PROXIES = [
    "http://qJl9qiKZnJ:TUx3MBeLrU@185.200.188.100:41403",
    "http://yXEwruw6Sk:9zN5auC9x5@103.82.103.157:58020",
    "http://yf3HaMfY7U:MdGUgUkVKs@103.127.77.179:62868",
    "http://CryQV1c3lo:pjXmuWtdeh@103.82.103.17:59750",
    "http://DvYemkIajY:uoSe6oN3RQ@45.158.198.88:40172",
    "http://YHMI2bDrbg:jwaAI5v6IS@45.132.252.133:53570",
    "http://m8IY2bBm6i:F1O2ykVyiu@45.154.247.22:63275",
    "http://NaTLKpP86D:b35iXcQ25L@103.82.103.253:47798",
    "http://Z7f0lVoTgu:jyMDFnmlqs@45.132.252.17:20890",
    "http://Jls7tshfC7:yiESYD0iJt@193.168.224.143:51312",
]

random.shuffle(PROXIES)

PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() in {"1", "true", "yes"}
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

_proxy_last_used: dict[str, float] = {}
next_request_time: float = 0.0
_session: YandexBrowserSession | None = None


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


def _pick_proxy(proxies: str | Sequence[str]) -> str:
    if isinstance(proxies, str):
        _proxy_last_used[proxies] = time.monotonic()
        return proxies

    if not proxies:
        raise ValueError("proxies list is empty")

    proxy = min(proxies, key=lambda p: _proxy_last_used.get(p, 0.0))
    _proxy_last_used[proxy] = time.monotonic()
    return proxy


def _parse_proxy(proxy_url: str) -> dict[str, str]:
    parsed = urlparse(proxy_url)
    config: dict[str, str] = {
        "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
    }
    if parsed.username:
        config["username"] = parsed.username
    if parsed.password:
        config["password"] = parsed.password
    return config


class YandexCaptchaError(RuntimeError):
    pass


def set_captcha_wait_callback(callback: Callable[[], Awaitable[None]] | None) -> None:
    global _captcha_wait_callback
    _captcha_wait_callback = callback


async def _is_captcha_page(page: Page) -> bool:
    if "checkcaptcha" in page.url:
        return True
    return bool(await page.locator('h1:has-text("робот")').count())


def _captcha_wait_timeout_ms() -> int:
    if MACBOOK and sys.platform == "darwin" and not PLAYWRIGHT_HEADLESS:
        return CAPTCHA_WAIT_TIMEOUT_MS
    return HEADLESS_CAPTCHA_WAIT_MS


async def _wait_for_search_results(page: Page, *, captcha_detected: bool) -> None:
    timeout_ms = _captcha_wait_timeout_ms() if captcha_detected else 150_000
    try:
        await page.wait_for_selector(SEARCH_RESULTS_SELECTOR, timeout=timeout_ms)
    except Exception as error:
        raise YandexCaptchaError("Timed out waiting for Yandex search results after captcha") from error


class YandexBrowserSession:
    def __init__(
        self,
        cookies_path: Path = COOKIES_PATH,
        proxies: Sequence[str] = PROXIES,
    ) -> None:
        self._cookies_path = cookies_path
        self._proxies = proxies
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        if self._page is not None:
            return

        proxy = _parse_proxy(_pick_proxy(self._proxies))
        cookies = load_yandex_cookies(self._cookies_path)

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=PLAYWRIGHT_HEADLESS,
            proxy=proxy,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = await self._browser.new_context(
            locale="ru-RU",
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 900},
        )
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        await self._context.add_cookies(cookies)
        self._page = await self._context.new_page()

    async def stop(self) -> None:
        if self._page is not None:
            await self._page.close()
            self._page = None
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def search(self, query: str, region: str = "санкт-петербург") -> AsyncGenerator[list[dict], None]:
        if self._page is None:
            raise RuntimeError("Browser session is not started")

        async with self._lock:
            soup = await _fetch_page(self._page, _build_search_url(rewrite_query(query, region)))
            yield _parse_results(soup)

            for pager_url in _parse_pager(soup)[:3]:
                try:
                    soup = await _fetch_page(self._page, pager_url)
                    yield _parse_results(soup)
                except YandexCaptchaError as error:
                    print(error)
                    break


async def init_browser_session(
    cookies_path: Path = COOKIES_PATH,
    proxies: Sequence[str] = PROXIES,
) -> YandexBrowserSession:
    global _session
    if _session is None:
        _session = YandexBrowserSession(cookies_path=cookies_path, proxies=proxies)
        await _session.start()
    return _session


async def close_browser_session() -> None:
    global _session
    if _session is not None:
        await _session.stop()
        _session = None


def get_browser_session() -> YandexBrowserSession:
    if _session is None:
        raise RuntimeError("Browser session is not started")
    return _session


def _build_search_url(query: str) -> str:
    params: dict[str, str | int] = {"text": query}
    return f"{YANDEX_SEARCH_URL}?{urlencode(params)}"


async def _fetch_page(page: Page, url: str) -> BeautifulSoup:
    global next_request_time

    now = time.monotonic()
    if now < next_request_time:
        await asyncio.sleep(next_request_time - now)
        await asyncio.sleep(random.uniform(0.1, 1))
        return await _fetch_page(page, url)
    next_request_time = time.monotonic() + random.uniform(5, 10)

    await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

    captcha_detected = await _is_captcha_page(page)
    if captcha_detected:
        notify_captcha()
        if _captcha_wait_callback is not None:
            await _captcha_wait_callback()

    await _wait_for_search_results(page, captcha_detected=captcha_detected)
    return BeautifulSoup(await page.content(), "html.parser")


def _parse_results(soup: BeautifulSoup) -> list[dict]:
    results: list[dict] = []
    ul = soup.find("ul", id="search-result")
    if not ul:
        print("NO UL")
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


def _parse_pager(soup: BeautifulSoup) -> list[str]:
    pager = soup.select_one(".Pager")
    if not pager:
        return []

    urls: list[str] = []
    for a in pager.select("a"):
        href = a.get("href")
        if href:
            urls.append("https://yandex.ru" + href)

    return urls


async def search_yandex(query: str, region: str = "санкт-петербург") -> AsyncGenerator[list[dict], None]:
    session = get_browser_session()
    async for results in session.search(query, region):
        yield results


async def _main() -> None:
    await init_browser_session()
    try:
        for i in range(4, 17):
            query = f"айфон {i}"
            try:
                print(f"searching {query}")
                async for results in search_yandex(query, region="санкт-петербург"):
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

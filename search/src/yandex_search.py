from __future__ import annotations

import asyncio
import json
import os
import random
import re
import time
from collections.abc import AsyncGenerator
from pathlib import Path
from urllib.parse import urlparse
import uuid

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright

from get_favicon import _default_favicon, get_favicon
from query_rewrite import rewrite_query

YA_RU_URL = "https://ya.ru/"
COOKIES_PATH = Path(__file__).resolve().parent.parent / "yandex_cookies.json"
SEARCH_INPUT_SELECTOR = "textarea#text"
TOP_SITES = 3

USER_AGENTS = [
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.2 Safari/605.1.15"
    ),
]

load_dotenv()

PROXY = os.getenv("PROXY")
PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() in {"1", "true", "yes"}
CAPTCHA_WAIT_TIMEOUT_MS = int(os.getenv("CAPTCHA_WAIT_TIMEOUT_MS", "1800000"))
HEADLESS_CAPTCHA_WAIT_MS = int(os.getenv("HEADLESS_CAPTCHA_WAIT_MS", "120000"))
SEARCH_RESULTS_SELECTOR = "ul#search-result li.serp-item"

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

scroll_speed_factor = 0.5
type_speed_factor = 0.3

REQUEST_SLEEP_SECONDS = (7.0, 14.0)
SCROLL_TARGET_DEPTH_FRACTION = (0.55 * scroll_speed_factor, 0.95 * scroll_speed_factor)
SCROLL_BACK_UP_CHANCE = 0.12 * scroll_speed_factor
SCROLL_BACK_UP_VIEWPORT_FRACTION = (0.05 * scroll_speed_factor, 0.2 * scroll_speed_factor)
SCROLL_DOWN_VIEWPORT_FRACTION = (0.12 * scroll_speed_factor, 0.5 * scroll_speed_factor)
SCROLL_STEP_PAUSE_SECONDS = (0.08 * scroll_speed_factor, 0.35 * scroll_speed_factor)
SCROLL_LONG_PAUSE_CHANCE = 0.2 * scroll_speed_factor
SCROLL_LONG_PAUSE_SECONDS = (0.25 * scroll_speed_factor, 0.85 * scroll_speed_factor)
TYPE_SPACE_DELAY_MS = (int(40 * type_speed_factor), int(110 * type_speed_factor))
TYPE_SPACE_PAUSE_SECONDS = (0.05 * type_speed_factor, 0.25 * type_speed_factor)
TYPE_CHUNK_DELAY_MS = (int(60 * type_speed_factor), int(180 * type_speed_factor))
TYPE_CHUNK_PAUSE_SECONDS = (0.15 * type_speed_factor, 0.55 * type_speed_factor)
TYPE_FINISH_PAUSE_SECONDS = (1 * type_speed_factor, 2 * type_speed_factor)

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


def _pick_user_agent() -> str:
    return random.choice(USER_AGENTS)


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


async def _is_captcha_page(page: Page) -> bool:
    if "checkcaptcha" in page.url:
        return True
    return bool(await page.locator('h1:has-text("робот")').count())


def _captcha_wait_timeout_ms() -> int:
    if PLAYWRIGHT_HEADLESS:
        return HEADLESS_CAPTCHA_WAIT_MS
    return CAPTCHA_WAIT_TIMEOUT_MS


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
        proxy: str | None = PROXY,
    ) -> None:
        self._cookies_path = cookies_path
        self._proxy_url = proxy
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._home_page: Page | None = None
        self._proxy: dict[str, str] | None = None
        self._user_agent: str | None = None

    async def start(self) -> None:
        if self._context is not None:
            return

        if not self._proxy_url:
            raise ValueError("PROXY environment variable is not set")

        self._proxy = _parse_proxy(self._proxy_url)
        self._user_agent = _pick_user_agent()
        cookies = load_yandex_cookies(self._cookies_path)

        print(f"browser session: proxy={self._proxy['server']} user_agent={self._user_agent!r}")

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=PLAYWRIGHT_HEADLESS,
            proxy=self._proxy,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = await self._browser.new_context(
            locale="ru-RU",
            user_agent=self._user_agent,
            viewport={"width": 1440, "height": 900},
        )
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        await self._context.add_cookies(cookies)
        self._home_page = await self._context.new_page()
        await self._home_page.goto(YA_RU_URL, wait_until="domcontentloaded", timeout=30_000)

    async def stop(self) -> None:
        self._home_page = None
        self._proxy = None
        self._user_agent = None
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def new_tab(self) -> Page:
        if self._context is None:
            raise RuntimeError("Browser session is not started")
        return await self._context.new_page()

    async def _open_search_tab(self) -> Page:
        return await self.new_tab()

    async def search(
        self,
        query: str,
        region: str = "санкт-петербург",
    ) -> AsyncGenerator[list[dict], None]:
        if self._context is None:
            raise RuntimeError("Browser session is not started")

        rewritten_query = rewrite_query(query, region)
        page = await self._open_search_tab()
        try:
            await _submit_search(page, rewritten_query)
            sites = _sites_from_discovery(_parse_site_results(await _current_soup(page)))
            await _attach_favicons(sites)
            yield sites

            for site in list(sites):
                site_query = f"site:{site['hostname']} {query.strip()}"
                await _submit_search(page, site_query)
                site["products"] = _parse_offer_results(await _current_soup(page))
                if not site["products"]:
                    sites.remove(site)
                yield sites
        finally:
            await page.close()


async def init_browser_session(
    cookies_path: Path = COOKIES_PATH,
    proxy: str | None = PROXY,
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


async def _handle_captcha(page: Page) -> bool:
    return await _is_captcha_page(page)


async def _wait_for_results(page: Page, *, captcha_detected: bool) -> None:
    await _wait_for_search_results(page, captcha_detected=captcha_detected)
    await _scroll_page_chaotically(page)
    global next_request_time
    next_request_time = time.monotonic() + random.uniform(*REQUEST_SLEEP_SECONDS)


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
            await search_input.press_sequentially(
                " ",
                delay=random.randint(*TYPE_SPACE_DELAY_MS),
            )
            await _human_pause(*TYPE_SPACE_PAUSE_SECONDS)
        await search_input.press_sequentially(
            chunk,
            delay=random.randint(*TYPE_CHUNK_DELAY_MS),
        )
        if index < len(chunks) - 1:
            await _human_pause(*TYPE_CHUNK_PAUSE_SECONDS)

    await _human_pause(*TYPE_FINISH_PAUSE_SECONDS)


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
    await page.goto(YA_RU_URL, wait_until="domcontentloaded", timeout=30_000)

    captcha_detected = await _handle_captcha(page)
    if captcha_detected:
        await _wait_for_search_results(page, captcha_detected=True)

    search_input = page.locator(SEARCH_INPUT_SELECTOR)
    await search_input.wait_for(state="visible", timeout=30_000)
    await search_input.click()
    await _human_pause(0.15, 0.45)
    await _type_query_naturally(search_input, query)
    await search_input.press("Enter")
    await _human_pause(0.5, 1.2)

    captcha_detected = await _handle_captcha(page)
    await _wait_for_results(page, captcha_detected=captcha_detected)


async def _favicon_for_site(site: dict) -> str:
    url = site.get("href") or f"https://{site['hostname']}/"
    try:
        favicon = await get_favicon(url)
    except Exception:
        favicon = None
    return favicon or _default_favicon(url)


async def _attach_favicons(sites: list[dict]) -> None:
    favicons = await asyncio.gather(*(_favicon_for_site(site) for site in sites))
    for site, favicon in zip(sites, favicons, strict=True):
        site["favicon"] = favicon


def _sites_from_discovery(site_results: list[dict], limit: int = TOP_SITES) -> list[dict]:
    sites: list[dict] = []
    seen: set[str] = set()
    for result in site_results:
        hostname = result.get("hostname")
        if not hostname or hostname in seen:
            continue
        seen.add(hostname)
        sites.append({
            "hostname": hostname,
            "href": result.get("href"),
            "rating": result.get("rating"),
            "reviews": result.get("reviews"),
            "delivery": result.get("delivery"),
            "products": [],
        })
        if len(sites) >= limit:
            break
    return sites


def _element_text(element) -> str:
    if element is None:
        return ""
    text = element.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text)


def _iter_serp_items(soup: BeautifulSoup):
    ul = soup.find("ul", id="search-result")
    if not ul:
        return

    for li in ul.select("li.serp-item"):
        if li.select("div[class*='AdvLabel']"):
            continue
        yield li


def _parse_site_results(soup: BeautifulSoup) -> list[dict]:
    results: list[dict] = []

    for li in _iter_serp_items(soup):
        if not li.select_one("div.Verified_type_goods"):
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

        if title and hostname:
            results.append({
                "title": _element_text(title),
                "hostname": hostname,
                "href": href,
                "rating": rating,
                "reviews": reviews,
                "delivery": delivery_container,
            })

    return results


def _parse_offer_results(soup: BeautifulSoup) -> list[dict]:
    results: list[dict] = []

    for li in _iter_serp_items(soup):
        if not li.select_one("div.Organic_withOfferThumb"):
            continue

        title = li.select_one(".OrganicTitle-LinkText")
        url = li.select_one("a.OrganicTitle-Link")
        href = url.get("href") if url else None

        price_el = li.select_one(".EPriceGroup .EPriceGroup-Price .EPrice-Content")
        price = price_el.get("title") if price_el else None

        thumbnail_el = li.select_one(".EThumb img")
        thumbnail = thumbnail_el.get("src") if thumbnail_el else None

        description_el = li.select_one("span.OrganicTextContentSpan")
        description = _element_text(description_el) if description_el else None

        if title and href:
            entry: dict = {
                "title": _element_text(title),
                "href": href,
                "price": price,
                "thumbnail": thumbnail,
            }
            if description:
                entry["description"] = description
            results.append(entry)

    return results

async def search_yandex(
    query: str,
    region: str = "санкт-петербург",
) -> AsyncGenerator[list[dict], None]:
    rewritten_query = rewrite_query(query, region)
    session = get_browser_session()
    async for sites in session.search(query, region):
        yield sites


async def _main() -> None:
    await init_browser_session()
    try:
        query = "айфон 17"
        print(f"searching {query}")
        async for sites in search_yandex(query, region="санкт-петербург"):
            for site in sites:
                print(
                    f"{site['hostname']}: "
                    f"{len(site.get('products', []))} products"
                )
    except YandexCaptchaError as error:
        print(error)
    finally:
        await close_browser_session()


if __name__ == "__main__":
    asyncio.run(_main())

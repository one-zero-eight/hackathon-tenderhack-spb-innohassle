import _bootstrap  # noqa: F401

import asyncio
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Comment, Tag
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from env import Config
from query_rewrite import rewrite_query
from yandex_search import get_browser_session

logger = logging.getLogger(__name__)

_MAX_PRODUCTS_PER_PAGE = 5
_EXTRACT_PAGE_CONCURRENCY = max(1, int(os.getenv("EXTRACT_PAGE_CONCURRENCY", "5")))
PAGE_SEMAPHORE = asyncio.Semaphore(_EXTRACT_PAGE_CONCURRENCY)
_PAGE_LOAD_TIMEOUT_MS = 30_000
_JS_RENDER_TIMEOUT_MS = 15_000
LLM_SEMAPHORE = asyncio.Semaphore(1)

_REMOVE_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "link",
        "meta",
        "head",
        "header",
        "footer",
        "nav",
        "iframe",
        "embed",
        "object",
        "canvas",
        "input",
        "button",
        "select",
        "textarea",
        "label",
        "fieldset",
        "legend",
        "svg",
        "picture",
        "source",
        "video",
        "audio",
        "template",
        "slot",
        "dialog",
        "menu",
        "aside",
    }
)

# Unwrap instead of decompose — catalog pages often wrap <main> in <form>.
_UNWRAP_TAGS = frozenset({"form", "div", "span", "font", "center"})

_PRESERVE_ATTRS = frozenset({"href", "src", "alt", "title", "datetime"})

_CHROME_TAGS = frozenset(
    {
        "mvid-cookie-notification",
        "mvid-header",
        "mvid-header-container",
        "mvid-filters-chips",
        "mvid-bottom-links-collection",
        "mvid-modals-container",
        "mvid-product-breadcrumbs",
        "mvid-customer-service-description",
        "router-outlet",
        "jdiv",
        "jmotion",
    }
)

_CHROME_TAG_PREFIXES = (
    "mvid-header",
    "mvid-modals",
    "mvid-bottom-links",
    "mvid-cookie",
)

_NOISE_CLASS_ID = re.compile(
    r"cookie|consent|gdpr|breadcrumb|pagination|mini-?cart|cart-widget|"
    r"jivo|callback|envybox|whitesaas|me-talk|smartcaptcha|"
    r"site-header|site-footer|page-footer|main-menu|main-nav",
    re.IGNORECASE,
)

_SOCIAL_HREF = re.compile(
    r"(?:^|//)(?:www\.)?(?:vk\.com|t\.me|telegram\.me|wa\.me|whatsapp\.com|"
    r"max\.ru|youtube\.com|youtu\.be|tiktok\.com|instagram\.com|"
    r"facebook\.com|fb\.com|ok\.ru)/",
    re.IGNORECASE,
)

_WIDGET_HREF = re.compile(
    r"whitesaas\.com|envybox|me-talk\.ru|jivosite\.com|saas-support\.com|"
    r"smartcaptcha|policy-cookie|about-cookies|agreeCookies",
    re.IGNORECASE,
)

_NOISE_HREF = re.compile(
    r"/shops/|gcat_id=|sch_id=|/personal/cart|/checkout/|"
    r"/catalog/compare|/wishlist|/favorite|adriver\.ru|doubleclick\.net|"
    r"googlesyndication\.com|mc\.yandex\.ru/watch|an\.yandex\.ru",
    re.IGNORECASE,
)

_AD_IMG_SRC = re.compile(
    r"adriver\.ru|doubleclick\.net|googlesyndication\.com|"
    r"mc\.yandex\.ru/watch|an\.yandex\.ru",
    re.IGNORECASE,
)

_LOGO_IMAGE = re.compile(r"logo|icon|favicon|sprite|placeholder|1x1|pixel", re.IGNORECASE)

_NOISE_TEXT = re.compile(
    r"используем файлы cookie|cookie файлы|файлы cookies|"
    r"подарок за подписку|подписаться на рассылку|"
    r"заказать звонок|обратный звонок|виртуальный помощник|"
    r"чат с оператором|ждите звонка|написать в max|"
    r"товар добавлен в корзину|корзина пуста|в корзине пусто|"
    r"отзывы покупателей о товарах",
    re.IGNORECASE,
)

_PRICE_SIGNAL = re.compile(r"\d[\d\s]*(?:₽|руб\.?)", re.IGNORECASE)

_MIN_MAIN_CHARS = 200

_MIN_PAGE_CONTENT_CHARS = 1000

_MAX_PAGE_CHARS = 50_000

_EXTRACT_SYSTEM_PROMPT = """\
You extract product information from cleaned web page content.

The user message includes user_query: the rewritten search query the user used.
Use user_query only to disambiguate the page:
- decide which listed items match what the user is looking for
- pick relevant products when the page shows several items
- rank products by relevance to user_query

Do not copy details from user_query into the result unless they also appear on the page.
Page content is the source of truth for name, cost, description, and characteristics.

When the page focuses on one specific product, return that product in products.
When the page lists the same product multiple times (e.g. offers from different sellers) \
with similar prices, return one entry with the common product name and the first cost you see. \
Leave description null and characteristics empty unless they clearly apply to that one product.

When the page lists several different products, extract up to 5 products that best match user_query.
Prefer products clearly related to the query over unrelated catalog items.
Skip navigation, ads, accessories, and unrelated listings.

Always block and reject these pages — they are never product pages:
- NSFW, adult, pornographic, or sexually explicit content
- Dating, hookup, escort, or romance-matching services

For blocked pages return an empty products list, set message to "This is not a product page.", \
and do not extract or reproduce any content from the page.

When the page is not about purchasable products at all (article, FAQ, login page, empty page), \
return an empty products list and set message to "This is not a product page."

When you successfully extract products, leave message null.

For each product return:
- name: product title as shown on the page
- cost: price in format "<number> ₽" with a space as thousands separator (e.g. "24 900 ₽", "79 990 ₽")
- description: short product description or summary
- characteristics: technical specs and attributes as key-value pairs

Use null for missing text fields. Use an empty object for characteristics when none are found.
Do not invent data that is not present on the page.
Return at most 5 products."""

_llm_client: AsyncOpenAI | None = None


class ParsedProduct(BaseModel):
    name: str | None = None
    cost: str | None = None
    description: str | None = None
    characteristics: dict[str, str] = Field(default_factory=dict)
    thumbnail: str | None = None


@dataclass(frozen=True)
class ExtractTimings:
    fetch_s: float
    clean_s: float
    llm_s: float
    total_s: float


class ParsedPageProducts(BaseModel):
    products: list[ParsedProduct] = Field(
        default_factory=list, max_length=_MAX_PRODUCTS_PER_PAGE
    )
    message: str | None = None


class ParsedSearchResult(BaseModel):
    products: list[ParsedProduct] = Field(default_factory=list)


def _get_llm_client() -> AsyncOpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = AsyncOpenAI(
            api_key=Config.LLM_API_KEY,
            base_url=Config.LLM_API_BASE_URL,
        )
    return _llm_client


def _tag_local_name(tag: Tag) -> str:
    return (tag.name or "").lower()


def _element_attr_text(tag: Tag) -> str:
    attrs = tag.attrs
    if not attrs:
        return ""
    parts: list[str] = []
    for key in ("id", "class", "role"):
        value = attrs.get(key)
        if not value:
            continue
        if isinstance(value, list):
            parts.extend(str(v) for v in value)
        else:
            parts.append(str(value))
    return " ".join(parts)


def _attr_str(tag: Tag, key: str) -> str:
    attrs = tag.attrs
    if not attrs:
        return ""
    value = attrs.get(key)
    if not value:
        return ""
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value)


def _href_value(tag: Tag) -> str:
    return _attr_str(tag, "href")


def _src_value(tag: Tag) -> str:
    return _attr_str(tag, "src")


def _parse_int(value: str) -> int | None:
    if not value:
        return None
    digits = re.sub(r"[^\d]", "", value)
    if not digits:
        return None
    return int(digits)


def _absolute_image_url(page_url: str, value: str) -> str | None:
    value = value.strip()
    if not value or value.startswith("data:"):
        return None
    absolute = urljoin(page_url, value)
    if _AD_IMG_SRC.search(absolute):
        return None
    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"}:
        return None
    return absolute


def _image_url_score(url: str, *, width: int | None = None, height: int | None = None) -> int:
    score = 0
    if width and height:
        if width < 40 or height < 40:
            return -1
        score += width * height
    if _LOGO_IMAGE.search(url):
        score -= 10_000
    return score


def _meta_thumbnail(soup: BeautifulSoup, page_url: str) -> str | None:
    selectors = (
        ('meta[property="og:image:secure_url"]', "content"),
        ('meta[property="og:image"]', "content"),
        ('meta[property="og:image:url"]', "content"),
        ('meta[name="twitter:image"]', "content"),
        ('link[rel="image_src"]', "href"),
    )
    best: tuple[int, str] | None = None
    for selector, attr in selectors:
        for element in soup.select(selector):
            url = _absolute_image_url(page_url, _attr_str(element, attr))
            if not url:
                continue
            score = _image_url_score(url) + (100_000 if "secure_url" in selector else 0)
            if best is None or score > best[0]:
                best = (score, url)
    return best[1] if best and best[0] >= 0 else None


def _content_thumbnail(soup: BeautifulSoup, page_url: str) -> str | None:
    root = _best_content_root(soup)
    best: tuple[int, str] | None = None
    for img in root.find_all("img"):
        url = _absolute_image_url(page_url, _src_value(img))
        if not url:
            continue
        score = _image_url_score(
            url,
            width=_parse_int(_attr_str(img, "width")),
            height=_parse_int(_attr_str(img, "height")),
        )
        alt = _attr_str(img, "alt")
        if alt and len(alt) > 3:
            score += 1000
        if best is None or score > best[0]:
            best = (score, url)
    return best[1] if best and best[0] >= 0 else None


def _parse_page_thumbnail(soup: BeautifulSoup, page_url: str) -> str | None:
    return _meta_thumbnail(soup, page_url) or _content_thumbnail(soup, page_url)


def _resolve_thumbnail(
    page_thumbnail: str | None,
    serp_thumbnail: str | None,
) -> str | None:
    return page_thumbnail or serp_thumbnail


def _apply_product_thumbnails(
    parsed: ParsedPageProducts,
    page_thumbnail: str | None,
    serp_thumbnail: str | None,
) -> None:
    fallback = _resolve_thumbnail(page_thumbnail, serp_thumbnail)
    for product in parsed.products:
        if not product.thumbnail:
            product.thumbnail = fallback


def _price_signal_score(text: str) -> int:
    return len(_PRICE_SIGNAL.findall(text)) * 500


def _catalog_article_page(body: Tag) -> bool:
    articles = body.find_all("article")
    return len(articles) > 3


def _best_content_root(soup: BeautifulSoup) -> Tag:
    body = soup.body
    if body is None:
        return soup

    main = body.find("main")
    if main is not None:
        text = main.get_text(" ", strip=True)
        if len(text) >= _MIN_MAIN_CHARS:
            return main

    if _catalog_article_page(body):
        return body

    best: Tag | None = None
    best_score = 0
    for tag in body.find_all("article"):
        text = tag.get_text(" ", strip=True)
        if len(text) < _MIN_MAIN_CHARS:
            continue
        score = len(text) + _price_signal_score(text)
        if score > best_score:
            best_score = score
            best = tag

    if best is not None:
        return best
    return body


def _page_content(soup: BeautifulSoup) -> str:
    root = _best_content_root(soup)
    content = root.get_text("\n", strip=True)
    if len(content) <= _MAX_PAGE_CHARS:
        return content
    return content[:_MAX_PAGE_CHARS] + "\n...[truncated]"


def _is_chrome_tag(tag: Tag) -> bool:
    name = _tag_local_name(tag)
    if name in _CHROME_TAGS:
        return True
    return any(name.startswith(prefix) for prefix in _CHROME_TAG_PREFIXES)


def _remove_comments(soup: BeautifulSoup) -> None:
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()


def _remove_by_class_id_role(soup: BeautifulSoup) -> None:
    for tag in list(soup.find_all(True)):
        if not isinstance(tag, Tag):
            continue
        attr_text = _element_attr_text(tag)
        if attr_text and _NOISE_CLASS_ID.search(attr_text):
            tag.decompose()
            continue
        role = _attr_str(tag, "role")
        if role.lower() in {
            "navigation",
            "banner",
            "contentinfo",
            "complementary",
            "dialog",
        }:
            tag.decompose()


def _remove_chrome_tags(soup: BeautifulSoup) -> None:
    for tag in list(soup.find_all(True)):
        if isinstance(tag, Tag) and _is_chrome_tag(tag):
            tag.decompose()


def _remove_tracking_images(soup: BeautifulSoup) -> None:
    for img in list(soup.find_all("img")):
        src = _src_value(img)
        if not src:
            continue
        if _AD_IMG_SRC.search(src):
            img.decompose()
            continue
        width = _attr_str(img, "width")
        height = _attr_str(img, "height")
        if width in ("0", "1") and height in ("0", "1"):
            img.decompose()


def _remove_noise_links(soup: BeautifulSoup) -> None:
    for anchor in list(soup.find_all("a", href=True)):
        href = _href_value(anchor)
        if not href:
            continue
        if _SOCIAL_HREF.search(href) or _WIDGET_HREF.search(href):
            anchor.decompose()
            continue
        if _NOISE_HREF.search(href) and len(anchor.get_text(strip=True)) < 80:
            anchor.decompose()


def _remove_link_farms(soup: BeautifulSoup) -> None:
    for container in list(soup.find_all(["ul", "ol", "nav", "div"])):
        links = container.find_all("a", href=True)
        if len(links) < 10:
            continue
        noise = sum(1 for link in links if _NOISE_HREF.search(_href_value(link)))
        if noise / len(links) >= 0.7:
            container.decompose()


def _remove_small_noise_blocks(soup: BeautifulSoup) -> None:
    for tag in list(soup.find_all(True)):
        if not isinstance(tag, Tag):
            continue
        text = tag.get_text(" ", strip=True)
        if not text or len(text) > 400:
            continue
        if _NOISE_TEXT.search(text):
            tag.decompose()


def _focus_main_content(soup: BeautifulSoup) -> None:
    body = soup.body
    if body is None:
        return

    main = body.find("main")
    if main is None:
        return

    text = main.get_text(" ", strip=True)
    if len(text) < _MIN_MAIN_CHARS:
        return

    focused = soup.new_tag("body")
    focused.append(main.extract())
    body.replace_with(focused)


def _decompose_remove_tags(soup: BeautifulSoup) -> None:
    for tag_name in _REMOVE_TAGS:
        for element in soup.find_all(tag_name):
            element.decompose()


def _unwrap_tags(soup: BeautifulSoup) -> None:
    for tag_name in _UNWRAP_TAGS:
        for element in list(soup.find_all(tag_name)):
            element.unwrap()


def _strip_attributes(soup: BeautifulSoup) -> None:
    for element in soup.find_all(True):
        attrs = element.attrs
        if not attrs:
            continue
        element.attrs = {
            key: value for key, value in attrs.items() if key in _PRESERVE_ATTRS
        }


def _clean_page_sync(soup: BeautifulSoup) -> BeautifulSoup:
    _remove_comments(soup)
    _remove_by_class_id_role(soup)
    _remove_chrome_tags(soup)
    _remove_tracking_images(soup)
    _remove_noise_links(soup)
    _remove_link_farms(soup)
    _focus_main_content(soup)
    _decompose_remove_tags(soup)
    _remove_small_noise_blocks(soup)
    _unwrap_tags(soup)
    _strip_attributes(soup)
    return soup


os.makedirs("cleaning", exist_ok=True)


async def _clean_page(soup: BeautifulSoup) -> BeautifulSoup:
    page_uuid = uuid.uuid4()
    print("Cleaning page...")

    with open(f"cleaning/{page_uuid}-original.html", "w") as f:
        f.write(soup.prettify())

    soup = _clean_page_sync(soup)

    with open(f"cleaning/{page_uuid}-cleaned.html", "w") as f:
        f.write(soup.prettify())

    return soup


async def _fetch_rendered_html(url: str) -> str:
    session = get_browser_session()
    async with PAGE_SEMAPHORE:
        page = await session.new_tab()
        try:
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=_PAGE_LOAD_TIMEOUT_MS,
            )
            try:
                await page.wait_for_load_state(
                    "networkidle",
                    timeout=_JS_RENDER_TIMEOUT_MS,
                )
            except Exception:
                pass
            return await page.content()
        finally:
            await page.close()


async def _extract_products(
    soup: BeautifulSoup,
    user_query: str,
    url: str,
    region: str = "санкт-петербург",
    serp_price: str | None = None,
    serp_thumbnail: str | None = None,
    page_thumbnail: str | None = None,
) -> ParsedPageProducts:
    rewritten_query = rewrite_query(user_query, region)
    serp_context = ""
    if serp_price:
        serp_context = f"SERP price: {serp_price}\n\n"
    user_content = (
        f"User query: {rewritten_query}\n\n"
        f"Page URL: {url}\n\n"
        f"{serp_context}"
        f"Page content:\n{_page_content(soup)}"
    )
    input_chars = len(_EXTRACT_SYSTEM_PROMPT) + len(user_content)

    llm_started = time.perf_counter()
    async with LLM_SEMAPHORE:
        completion = await _get_llm_client().chat.completions.parse(
            model=Config.LLM_MODEL,
            messages=[
                {"role": "system", "content": _EXTRACT_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format=ParsedPageProducts,
        )
    llm_seconds = time.perf_counter() - llm_started

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError(f"LLM returned no structured product data for {url}")
    parsed.products = parsed.products[:_MAX_PRODUCTS_PER_PAGE]
    _apply_product_thumbnails(parsed, page_thumbnail, serp_thumbnail)

    output_chars = len(parsed.model_dump_json())
    total_chars = input_chars + output_chars
    chars_per_second = total_chars / llm_seconds if llm_seconds > 0 else 0.0
    print(
        f"extract llm: {llm_seconds:.2f}s, "
        f"{chars_per_second:.0f} chars/s "
        f"({input_chars} in + {output_chars} out), "
        f"url={url}",
        flush=True,
    )
    return parsed


async def extract_products(
    url: str,
    user_query: str,
    region: str = "санкт-петербург",
    serp_price: str | None = None,
    serp_thumbnail: str | None = None,
) -> tuple[ParsedPageProducts, ExtractTimings]:
    total_started = time.perf_counter()
    fetch_started = time.perf_counter()
    html = await _fetch_rendered_html(url)
    fetch_s = time.perf_counter() - fetch_started

    clean_started = time.perf_counter()
    soup = BeautifulSoup(html, "html.parser")
    page_thumbnail = _parse_page_thumbnail(soup, url)
    soup = await _clean_page(soup)
    clean_s = time.perf_counter() - clean_started

    llm_s = 0.0
    if len(_page_content(soup)) < _MIN_PAGE_CONTENT_CHARS:
        result = ParsedPageProducts(message="This is not a product page.")
    else:
        llm_started = time.perf_counter()
        result = await _extract_products(
            soup,
            user_query,
            url,
            region,
            serp_price,
            serp_thumbnail,
            page_thumbnail,
        )
        llm_s = time.perf_counter() - llm_started

    total_s = time.perf_counter() - total_started
    timings = ExtractTimings(
        fetch_s=fetch_s,
        clean_s=clean_s,
        llm_s=llm_s,
        total_s=total_s,
    )
    logger.info(
        "extract page: total=%.2fs fetch=%.2fs clean=%.2fs llm=%.2fs url=%s",
        total_s,
        fetch_s,
        clean_s,
        llm_s,
        url,
    )
    return result, timings

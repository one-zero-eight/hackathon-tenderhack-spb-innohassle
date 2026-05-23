import asyncio
from typing import Any

import httpx
from bs4 import BeautifulSoup, Comment
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from env import Config
from query_rewrite import rewrite_query

_MAX_PRODUCTS_PER_PAGE = 5
HTTP_SEMAPHORE = asyncio.Semaphore(10)
LLM_SEMAPHORE = asyncio.Semaphore(8)

_REMOVE_TAGS = frozenset({
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
    "form",
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
})

_UNWRAP_TAGS = frozenset({"div", "span", "font", "center"})

_PRESERVE_ATTRS = frozenset({"href", "src", "alt", "title", "datetime"})

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

When the page is not about purchasable products at all (article, FAQ, login page, empty page), \
return an empty products list.

For each product return:
- name: product title as shown on the page
- cost: price with currency if present (e.g. "79 990 ₽")
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


class ParsedPageProducts(BaseModel):
    products: list[ParsedProduct] = Field(default_factory=list, max_length=_MAX_PRODUCTS_PER_PAGE)


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


def _page_content(soup: BeautifulSoup) -> str:
    root = soup.find("main") or soup.find("article") or soup.body or soup
    content = root.get_text("\n", strip=True)
    if len(content) <= _MAX_PAGE_CHARS:
        return content
    return content[:_MAX_PAGE_CHARS] + "\n...[truncated]"


async def _clean_page(soup: BeautifulSoup) -> BeautifulSoup:
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    for tag_name in _REMOVE_TAGS:
        for element in soup.find_all(tag_name):
            element.decompose()

    for tag_name in _UNWRAP_TAGS:
        for element in soup.find_all(tag_name):
            element.unwrap()

    for element in soup.find_all(True):
        element.attrs = {
            key: value
            for key, value in element.attrs.items()
            if key in _PRESERVE_ATTRS
        }

    return soup


async def _extract_products(
    soup: BeautifulSoup,
    user_query: str,
    url: str,
    region: str = "санкт-петербург",
) -> list[ParsedProduct]:
    rewritten_query = rewrite_query(user_query, region)
    async with LLM_SEMAPHORE:
        completion = await _get_llm_client().chat.completions.parse(
            model=Config.LLM_MODEL,
            messages=[
                {"role": "system", "content": _EXTRACT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"User query: {rewritten_query}\n\n"
                        f"Page URL: {url}\n\n"
                        f"Page content:\n{_page_content(soup)}"
                    ),
                },
            ],
            response_format=ParsedPageProducts,
        )

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError(f"LLM returned no structured product data for {url}")
    return parsed.products[:_MAX_PRODUCTS_PER_PAGE]


async def extract_products(
    client: httpx.AsyncClient,
    url: str,
    user_query: str,
    region: str = "санкт-петербург",
) -> list[ParsedProduct]:
    async with HTTP_SEMAPHORE:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    soup = await _clean_page(soup)
    return await _extract_products(soup, user_query, url, region)

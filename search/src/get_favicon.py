from __future__ import annotations

from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

DEFAULT_TIMEOUT = 10.0
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


def _normalize_rel(rel: str | list[str]) -> str:
    if isinstance(rel, list):
        return " ".join(rel).lower()
    return rel.lower()


def _resolve_url(base_url: str, href: str | None) -> str | None:
    if not href or not href.strip():
        return None
    return urljoin(base_url, href.strip())


def _find_favicon_in_html(html: str, page_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    for link in soup.find_all("link", href=True):
        rel = _normalize_rel(link.get("rel", ""))
        if "icon" not in rel.split():
            continue
        favicon_url = _resolve_url(page_url, link["href"])
        if favicon_url:
            return favicon_url

    for meta in soup.find_all("meta", content=True):
        name = (meta.get("name") or meta.get("property") or "").lower()
        if "icon" not in name:
            continue
        favicon_url = _resolve_url(page_url, meta["content"])
        if favicon_url:
            return favicon_url

    return None


def _default_favicon(url: str) -> str:
    parsed = urlparse(url)
    return urljoin(f"{parsed.scheme}://{parsed.netloc}/", "favicon.ico")


async def get_favicon(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> str | None:
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type and "<html" not in response.text[:500].lower():
        return None

    return _find_favicon_in_html(response.text, str(response.url)) or _default_favicon(url)


if __name__ == "__main__":
    import asyncio

    print(asyncio.run(get_favicon("https://www.cqham.ru/risearch_help.htm")))
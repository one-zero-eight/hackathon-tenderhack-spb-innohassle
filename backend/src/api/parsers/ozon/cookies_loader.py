from __future__ import annotations

import json
import logging
from pathlib import Path

from playwright.async_api import BrowserContext, Page

from src.api.parsers.playwright_page import goto

logger = logging.getLogger(__name__)

OZON_HOME = "https://www.ozon.ru/"


def load_cookies_file(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(path)

    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("cookies", data) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        raise ValueError("cookies.json: expected a list (Cookie-Editor format)")

    cookies: list[dict] = []
    for item in raw:
        name = item.get("name")
        value = item.get("value")
        if not name or value is None:
            continue
        entry: dict = {
            "name": name,
            "value": str(value),
            "domain": item.get("domain", ".ozon.ru"),
            "path": item.get("path", "/"),
        }
        if item.get("secure"):
            entry["secure"] = True
        if item.get("httpOnly"):
            entry["httpOnly"] = True
        same_site = item.get("sameSite")
        if same_site and str(same_site).lower() not in ("null", "none", ""):
            normalized = str(same_site).capitalize()
            if normalized in ("Lax", "Strict", "None"):
                entry["sameSite"] = normalized
        cookies.append(entry)
    return cookies


async def apply_cookies_to_context(
    context: BrowserContext,
    page: Page,
    cookies_path: Path,
    *,
    page_load_timeout: int = 20,
) -> int:
    """Load cookies.json into a CloakBrowser context (domain must be opened first)."""
    cookies = load_cookies_file(cookies_path)
    await goto(
        page,
        OZON_HOME,
        timeout_sec=float(page_load_timeout),
        wait_until="commit",
        retries=2,
    )
    await context.add_cookies(cookies)
    await page.reload(wait_until="commit", timeout=int(page_load_timeout * 1000))
    logger.info("Ozon cookies applied: %d from %s", len(cookies), cookies_path.name)
    return len(cookies)

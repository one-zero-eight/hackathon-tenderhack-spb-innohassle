from __future__ import annotations

import json
from pathlib import Path

from selenium.webdriver.remote.webdriver import WebDriver

from src.api.parsers.ozon.navigation import safe_get


def load_cookies_file(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(path)

    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("cookies", data) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        raise ValueError("cookies.json: ожидается список (формат Cookie-Editor)")

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
            s = str(same_site).capitalize()
            if s in ("Lax", "Strict", "None"):
                entry["sameSite"] = s
        cookies.append(entry)
    return cookies


def apply_cookies(
    driver: WebDriver,
    cookies_path: Path,
    *,
    base_url: str = "https://www.ozon.ru",
    via_proxy: bool = False,
    page_load_timeout: int | None = None,
    page_load_retries: int = 4,
) -> int:
    """Загружает cookies в браузер (сначала открывает домен)."""
    cookies = load_cookies_file(cookies_path)
    safe_get(
        driver,
        base_url,
        via_proxy=via_proxy,
        page_load_timeout=page_load_timeout,
        retries=page_load_retries,
    )
    added = 0
    for cookie in cookies:
        try:
            driver.add_cookie(cookie)
            added += 1
        except Exception:
            continue
    driver.refresh()
    return added


def resolve_cookies_path(path: Path | None) -> Path | None:
    if path is None:
        return None
    if path.is_absolute() and path.exists():
        return path
    candidates = [
        path,
        Path.cwd() / path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return path

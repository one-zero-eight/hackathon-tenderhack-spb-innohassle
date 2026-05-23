from __future__ import annotations

import json
import logging
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from selenium_driverless import webdriver

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProxySettings:
    """Настройки для Chrome --proxy-server (+ расширение при авторизации)."""

    server: str
    username: str | None = None
    password: str | None = None

    @property
    def has_auth(self) -> bool:
        return bool(self.username and self.password)

    def log_safe(self) -> str:
        if self.has_auth:
            parsed = urlparse(self.server)
            return f"{parsed.scheme}://***:***@{parsed.hostname}:{parsed.port}"
        return self.server


def parse_proxy(value: str) -> ProxySettings:
    """
    Форматы:
      http://127.0.0.1:8080
      socks5://127.0.0.1:1080
      http://user:pass@host:port
      user:pass@host:port
    """
    raw = value.strip()
    if not raw:
        raise ValueError("Пустой адрес прокси")

    parsed = urlparse(raw if "://" in raw else f"http://{raw}")
    scheme = (parsed.scheme or "http").lower()
    if scheme not in ("http", "https", "socks5", "socks4"):
        raise ValueError(f"Схема не поддерживается: {scheme}")

    host = parsed.hostname
    port = parsed.port
    if not host or not port:
        raise ValueError(
            "Укажите host и port, например: http://127.0.0.1:8080 или socks5://127.0.0.1:1080",
        )

    server = f"{scheme}://{host}:{port}"
    return ProxySettings(
        server=server,
        username=parsed.username,
        password=parsed.password,
    )


def _proxy_auth_extension(proxy: ProxySettings) -> Path:
    """ZIP-расширение Chrome для прокси с логином/паролем (без MV3 driverless)."""
    parsed = urlparse(proxy.server)
    host = parsed.hostname or ""
    port = parsed.port or 8080
    user_js = json.dumps(proxy.username or "")
    pass_js = json.dumps(proxy.password or "")
    scheme = parsed.scheme if parsed.scheme in ("http", "https", "socks4", "socks5") else "http"

    manifest = """{
  "version": "1.0.0",
  "manifest_version": 2,
  "name": "Ozon Proxy Auth",
  "permissions": [
    "proxy",
    "tabs",
    "unlimitedStorage",
    "storage",
    "<all_urls>",
    "webRequest",
    "webRequestBlocking"
  ],
  "background": {"scripts": ["background.js"]}
}
"""
    background = f"""
var config = {{
  mode: "fixed_servers",
  rules: {{
    singleProxy: {{ scheme: "{scheme}", host: "{host}", port: {port} }},
    bypassList: ["localhost", "127.0.0.1"]
  }}
}};
chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});

function callbackFn(details) {{
  return {{ authCredentials: {{ username: {user_js}, password: {pass_js} }} }};
}}
chrome.webRequest.onAuthRequired.addListener(
  callbackFn,
  {{ urls: ["<all_urls>"] }},
  ["blocking"]
);
"""

    tmp = Path(tempfile.mkdtemp(prefix="ozon_proxy_"))
    zip_path = tmp / "proxy_auth.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("manifest.json", manifest)
        zf.writestr("background.js", background)
    return zip_path


def apply_proxy(options: webdriver.ChromeOptions, proxy: ProxySettings | str | None) -> ProxySettings | None:
    """
    Настраивает прокси через аргументы Chrome.

    Не используем options.single_proxy: для него driverless ждёт свой MV3 service worker,
  что в headless часто падает с «Couldn't find mv3 extension within 10 seconds».
    """
    if not proxy:
        return None
    settings = parse_proxy(proxy) if isinstance(proxy, str) else proxy

    if settings.has_auth:
        options.use_extension = False
        options.add_extension(str(_proxy_auth_extension(settings)))
        logger.info("Прокси с авторизацией: %s", settings.log_safe())
    else:
        options.add_argument(f"--proxy-server={settings.server}")
        logger.info("Прокси: %s", settings.server)

    return settings

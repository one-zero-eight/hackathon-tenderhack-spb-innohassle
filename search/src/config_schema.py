from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field


def normalize_socks5_proxy_url(raw: str) -> str:
    """Normalize proxy to socks5:// for CloakBrowser."""
    value = raw.strip()
    if not value:
        raise ValueError("proxy entry is empty")
    if "://" not in value:
        return f"socks5://{value}"
    parsed = urlparse(value)
    if parsed.scheme in ("socks5", "socks5h"):
        return value
    if parsed.scheme in ("http", "https"):
        if not parsed.hostname:
            raise ValueError(f"invalid proxy URL: {raw!r}")
        return f"socks5://{parsed.netloc}"
    raise ValueError(
        f"yandex_search_settings: only socks5 proxy is supported, got {parsed.scheme!r}",
    )


class YandexSearchSettings(BaseModel):
    headless: bool = True
    "Run CloakBrowser without a visible window"
    humanize: bool = False
    "CloakBrowser human-like cursor/scroll behaviour"
    geoip: bool = True
    "Align timezone/locale with proxy geo (requires cloakbrowser[geoip])"
    proxy: str | None = None
    "Single SOCKS5 proxy: user:pass@host:port or socks5://user:pass@host:port"
    proxies: list[str] = Field(default_factory=list)
    "SOCKS5 proxy pool for CloakBrowser (ya.ru search); least-recently-used pick"

    def proxy_pool(self) -> list[str]:
        if self.proxy:
            return [normalize_socks5_proxy_url(self.proxy)]
        return [normalize_socks5_proxy_url(entry) for entry in self.proxies]


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    yandex_search_settings: YandexSearchSettings = Field(
        default_factory=YandexSearchSettings,
    )

    @classmethod
    def from_yaml(cls, path: Path) -> Settings:
        with path.open(encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        return cls.model_validate(data)

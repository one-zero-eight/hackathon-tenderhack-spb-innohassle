from __future__ import annotations

import random
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


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
    "SOCKS5 proxy pool; a random entry is used when proxy is not set"

    def resolve_proxy(self) -> str | None:
        raw = self.proxy
        if not raw and self.proxies:
            raw = random.choice(self.proxies)
        if not raw:
            return None
        value = raw.strip()
        if "://" not in value:
            return f"socks5://{value}"
        return value


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

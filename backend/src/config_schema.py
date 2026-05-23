import random
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class ApiSettings(BaseModel):
    app_root_path: str = Field("/api")
    'Prefix for the API path (e.g. "/api/v0")'
    cors_allow_origin_regex: str = ".*"
    "Allowed origins for CORS: from which domains requests to the API are allowed."
    db_url: SecretStr = Field(
        ...,
        examples=[
            "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
            "postgresql+asyncpg://postgres:postgres@db:5432/postgres",
        ],
    )
    "PostgreSQL database connection URL"
    secret_key: SecretStr = Field(...)


class AuthSettings(BaseModel):
    encryption_algorithm: str = "HS256"
    "The encryption algorithm for encryption/decryption in auth"
    access_token_ttl_minutes: int = 60
    "Access token expiration time in minutes"
    refresh_token_ttl_days: int = 7
    "Refresh token expiration time in days"
    leeway: int = 60
    "Leeway in seconds for clock skew"


class OzonSettings(BaseModel):
    headless: bool = True
    "Run Chrome without a visible window"
    geoip: bool = True
    humanize: bool = False
    slow: bool = False
    "Use longer pauses during warmup and scrolling to reduce blocking risk"
    proxy: str | None = None
    "Single proxy URL, e.g. socks5://user:pass@host:port"
    proxies: list[str] = Field(default_factory=list)
    "Proxy pool; a random entry is used when proxy is not set"
    page_load_timeout: int = 20
    "Max seconds to wait for Ozon page load"
    element_wait_timeout: int = 8
    "Max seconds to wait for search results and other DOM elements"
    page_load_retries: int = 1
    "How many times to retry opening a page after timeout"
    fetch_details: bool = False
    "Open each product page to read price (slower, like CLI --details)"
    composer_search: bool = True
    "Open search SERP in browser, then load products via composer-api (no DOM scroll)"
    composer_raw: bool = True
    "Fetch Ozon via composer-api HTTP; parse products on API layer (not in browser parser)"
    cookies_file: str | None = "cookies.json"
    "Path to cookies.json (relative to settings.yaml or cwd)"

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

    def resolve_cookies_path(self, *, settings_dir: Path | None = None) -> Path | None:
        if not self.cookies_file:
            return None
        path = Path(self.cookies_file)
        candidates = [path]
        if settings_dir:
            candidates.append(settings_dir / path)
        candidates.append(Path.cwd() / path)
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()
        return None


def _normalize_socks5_proxy_url(raw: str) -> str:
    """Yandex Market httpx uses SOCKS5 only."""
    value = raw.strip()
    if "://" not in value:
        return f"socks5://{value}"
    parsed = urlparse(value)
    if parsed.scheme in ("socks5", "socks5h"):
        return value
    if parsed.scheme in ("http", "https"):
        return f"socks5://{parsed.netloc}"
    raise ValueError(
        f"yandex_market_settings: only socks5 proxy is supported, got {parsed.scheme!r}",
    )


class BrowserPoolSettings(BaseModel):
    wildberries_pool_size: int = Field(2, ge=1, le=5)
    "Number of parallel Chrome sessions for Wildberries"
    ozon_pool_size: int = Field(2, ge=1, le=5)
    "Number of parallel Chrome sessions for Ozon"


class OllamaSettings(BaseModel):
    host: str = Field(
        default="http://ollama:11434",
        examples=["http://ollama:11434", "http://localhost:11434"],
    )
    "Base URL of the local Ollama server"
    model: str = Field(default="granite4.1:8b")
    "Model to use for relevance filtering"
    batch_size: int = Field(default=5, ge=1, le=20)
    "Products sent in a single LLM call. Keep small for compact models."
    concurrency: int = Field(default=4, ge=1, le=32)
    "Max number of simultaneous batch requests sent to Ollama."
    timeout: int = Field(default=60)
    "Seconds before an Ollama request is considered timed out"


class WildberriesSettings(BaseModel):
    headless: bool = True
    "Run Chrome without a visible window"
    chrome_executable_path: str | None = None
    "Path to Chrome/Chromium executable"
    proxy: str | None = None
    proxies: list[str] = Field(default_factory=list)
    page_load_timeout: int = 20
    "Max seconds to wait for Wildberries page load"
    element_wait_timeout: int = 8
    "Max seconds to wait for product cards in search results"
    page_load_retries: int = 1
    "How many times to retry opening search after anti-bot or empty page"

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


class YandexMarketSettings(BaseModel):
    proxy: str | None = None
    "SOCKS5 proxy for httpx: user:pass@host:port or socks5://user:pass@host:port"
    proxies: list[str] = Field(default_factory=list)
    "SOCKS5 proxy pool; a random entry is used when proxy is not set"
    timeout: int = 30
    "httpx request timeout in seconds"
    connect_timeout: int = 6
    "httpx connect timeout in seconds"
    request_retries: int = Field(3, ge=1, le=6)
    "Retries on proxy/connect errors (RemoteProtocolError, timeouts)"
    warmup: bool = True
    "Open market.yandex.ru once per client to obtain cookies before search"

    def resolve_proxy(self) -> str | None:
        raw = self.proxy
        if not raw and self.proxies:
            raw = random.choice(self.proxies)
        if not raw:
            return None
        return _normalize_socks5_proxy_url(raw)


class Settings(BaseModel):
    model_config = ConfigDict(json_schema_extra={"title": "Settings"}, extra="ignore")
    api_settings: ApiSettings
    auth_settings: AuthSettings
    ozon_settings: OzonSettings = Field(default_factory=OzonSettings)
    wildberries_settings: WildberriesSettings = Field(default_factory=WildberriesSettings)
    browser_pool_settings: BrowserPoolSettings = Field(default_factory=BrowserPoolSettings)
    yandex_market_settings: YandexMarketSettings = Field(default_factory=YandexMarketSettings)
    ollama_settings: OllamaSettings = Field(default_factory=OllamaSettings)

    @classmethod
    def from_yaml(cls, path: Path) -> "Settings":
        with open(path, encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)

        return cls.model_validate(yaml_config)

    @classmethod
    def save_schema(cls, path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            schema = {"$schema": "https://json-schema.org/draft-07/schema", **cls.model_json_schema()}
            yaml.dump(schema, f, sort_keys=False)

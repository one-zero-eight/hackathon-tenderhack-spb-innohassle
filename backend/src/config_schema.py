import random
from pathlib import Path

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
    nominatim_url: str = Field(
        default="http://nominatim:8080",
        examples=["http://nominatim:8080", "http://localhost:8080"],
    )
    "Base URL of the local Nominatim geocoding service (Docker service name by default)"


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
    cookies_file: str | None = "cookies.json"
    "Path to cookies.json (relative to settings.yaml or cwd)"

    def resolve_proxy(self) -> str | None:
        raw = self.proxy
        if not raw and self.proxies:
            raw = random.choice(self.proxies)
        if not raw:
            return None
        return raw if "://" in raw else f"http://{raw}"

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


class BrowserPoolSettings(BaseModel):
    wildberries_pool_size: int = Field(2, ge=1, le=5)
    "Number of parallel Chrome sessions for Wildberries"
    ozon_pool_size: int = Field(2, ge=1, le=5)
    "Number of parallel Chrome sessions for Ozon"


class YandexMarketSettings(BaseModel):
    proxy: str | None = None
    "Single proxy URL for httpx, e.g. http://user:pass@host:port"
    proxies: list[str] = Field(default_factory=list)
    "Proxy pool; a random entry is used when proxy is not set"
    timeout: int = 30
    "httpx request timeout in seconds"
    warmup: bool = True
    "Open market.yandex.ru once per client to obtain cookies before search"

    def resolve_proxy(self) -> str | None:
        raw = self.proxy
        if not raw and self.proxies:
            raw = random.choice(self.proxies)
        if not raw:
            return None
        return raw if "://" in raw else f"http://{raw}"


class WildberriesSettings(BaseModel):
    headless: bool = True
    "Run Chrome without a visible window"
    chrome_executable_path: str | None = None
    "Path to Chrome/Chromium executable"
    page_load_timeout: int = 20
    "Max seconds to wait for Wildberries page load"
    element_wait_timeout: int = 8
    "Max seconds to wait for product cards in search results"
    page_load_retries: int = 1
    "How many times to retry opening search after anti-bot or empty page"


class Settings(BaseModel):
    model_config = ConfigDict(json_schema_extra={"title": "Settings"}, extra="ignore")
    api_settings: ApiSettings
    auth_settings: AuthSettings
    ozon_settings: OzonSettings = Field(default_factory=OzonSettings)
    wildberries_settings: WildberriesSettings = Field(default_factory=WildberriesSettings)
    browser_pool_settings: BrowserPoolSettings = Field(default_factory=BrowserPoolSettings)
    yandex_market_settings: YandexMarketSettings = Field(default_factory=YandexMarketSettings)

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

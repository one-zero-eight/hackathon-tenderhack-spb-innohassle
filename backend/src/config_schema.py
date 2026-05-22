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
    page_load_timeout: int = 180
    "Max seconds to wait for Ozon page load"
    element_wait_timeout: int = 45
    "Max seconds to wait for search results and other DOM elements"
    page_load_retries: int = 4
    "How many times to retry opening a page after timeout"

    def resolve_proxy(self) -> str | None:
        if self.proxy:
            return self.proxy
        if self.proxies:
            return random.choice(self.proxies)
        return None


class Settings(BaseModel):
    model_config = ConfigDict(json_schema_extra={"title": "Settings"}, extra="ignore")
    api_settings: ApiSettings
    auth_settings: AuthSettings
    ozon_settings: OzonSettings = Field(default_factory=OzonSettings)

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

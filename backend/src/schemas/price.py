from typing import Literal

from pydantic import Field

from src.schemas.pydantic_base import BaseSchema


class PriceSearchRequest(BaseSchema):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=5, ge=1, le=100)
    skip: int = Field(default=0, ge=0)
    bypass_spellchecker: bool = False
    bypass_relevance_filter: bool = False
    relevance_quality: Literal["high", "medium", "low"] = Field(
        default="high",
        description=(
            "Controls the relevance filter accuracy/speed trade-off. "
            "\"high\" (default) uses chain-of-thought reasoning per product — most accurate. "
            "\"medium\" uses the detailed prompt but flat boolean output — accurate and fast. "
            "\"low\" returns a flat boolean list with a simpler prompt — fastest, fewer output tokens."
        ),
    )
    location: str | None = Field(
        default=None,
        description="City or region for regional pricing on WB, Yandex Market, and Ozon. Defaults to Moscow.",
    )
    ozon_composer_raw: bool | None = Field(
        default=None,
        description=(
            "If true, Ozon is loaded via composer-api HTTP (browser session) and parsed on this backend. "
            "If null, uses ozon_settings.composer_raw."
        ),
    )
    include_ozon_composer_data: bool = Field(
        default=False,
        description="Also stream raw composer JSON as type=ozon_composer (debug; large payloads).",
    )
    wb_search_api_raw: bool | None = Field(
        default=None,
        description=(
            "If true, Wildberries uses search.wb.ru via CloakBrowser HTTP and parses on this backend. "
            "If null, uses wildberries_settings.search_api_raw."
        ),
    )
    include_wb_search_api_data: bool = Field(
        default=False,
        description="Also stream raw search.wb.ru JSON as type=wb_search (debug).",
    )


class ProductPrice(BaseSchema):
    source: str
    price: float | None = None
    name: str | None = None
    brand: str | None = None
    original_price: float | None = None
    url: str | None = None
    image_url: str | None = None


class MarketplacePriceResult(BaseSchema):
    source: str
    prices: list[ProductPrice]
    error: str | None = None


class PriceSearchResponse(BaseSchema):
    query: str
    fixed_query: str | None = None
    results: list[MarketplacePriceResult]

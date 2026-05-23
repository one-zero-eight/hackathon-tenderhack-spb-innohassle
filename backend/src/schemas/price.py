from pydantic import Field

from src.schemas.pydantic_base import BaseSchema


class PriceSearchRequest(BaseSchema):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=5, ge=1, le=100)
    skip: int = Field(default=0, ge=0)
    bypass_spellchecker: bool = False
    location: str | None = Field(
        default=None,
        description="City or region for WB/Yandex regional pricing (e.g. 'Санкт-Петербург'). Defaults to Moscow.",
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

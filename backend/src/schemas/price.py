from pydantic import Field

from src.schemas.pydantic_base import BaseSchema


class PriceSearchRequest(BaseSchema):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=5, ge=1, le=20)


class ProductPrice(BaseSchema):
    source: str
    price: float
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
    results: list[MarketplacePriceResult]

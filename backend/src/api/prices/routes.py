import asyncio

from fastapi import APIRouter
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.api.parsers import parse_wildberries_products, parse_yandex_market_products
from src.schemas import MarketplacePriceResult, PriceSearchRequest, PriceSearchResponse, ProductPrice

router = APIRouter(prefix="/prices", tags=["Prices"], route_class=AutoDeriveResponsesAPIRoute)


@router.post("/search")
async def search_prices(payload: PriceSearchRequest) -> PriceSearchResponse:
    yandex_result, wildberries_result = await asyncio.gather(
        parse_yandex_market_products(payload.query, payload.limit, payload.skip, payload.location),
        parse_wildberries_products(payload.query, payload.limit, payload.skip, payload.location),
        return_exceptions=True,
    )

    return PriceSearchResponse(
        query=payload.query,
        results=[
            _build_yandex_market_result(yandex_result),
            _build_wildberries_result(wildberries_result),
        ],
    )


def _build_yandex_market_result(result: list[dict] | BaseException) -> MarketplacePriceResult:
    source = "Yandex Market"
    if isinstance(result, BaseException):
        return MarketplacePriceResult(source=source, prices=[], error=str(result))

    prices = [
        ProductPrice(
            source=source,
            name=item.get("name"),
            brand=item.get("brand"),
            price=float(item["sale_price"]),
            original_price=_optional_float(item.get("original_price")),
            url=_optional_str(item.get("url")),
            image_url=_optional_str(item.get("image_url")),
        )
        for item in result
        if item.get("sale_price") is not None
    ]
    return MarketplacePriceResult(source=source, prices=prices)


def _build_wildberries_result(result: list[dict] | BaseException) -> MarketplacePriceResult:
    source = "Wildberries"
    if isinstance(result, BaseException):
        return MarketplacePriceResult(source=source, prices=[], error=str(result))

    prices = [
        ProductPrice(
            source=source,
            name=item.get("name"),
            brand=item.get("brand"),
            price=float(item["sale_price"]),
            original_price=_optional_float(item.get("original_price")),
            url=_optional_str(item.get("url")),
            image_url=_optional_str(item.get("image_url")),
        )
        for item in result
        if item.get("sale_price") is not None
    ]
    return MarketplacePriceResult(source=source, prices=prices)


def _optional_float(value: object) -> float | None:
    return float(value) if value is not None else None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        first_string = next((item for item in value if isinstance(item, str)), None)
        return first_string
    return str(value)

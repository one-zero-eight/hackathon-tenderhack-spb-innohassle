import asyncio

from fastapi import APIRouter
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.api.parsers import parse_ozon_products, parse_wildberries_products, parse_yandex_market_products
from src.api.parsers.spellcheck import spellcheck
from src.schemas import MarketplacePriceResult, PriceSearchRequest, PriceSearchResponse, ProductPrice

router = APIRouter(prefix="/prices", tags=["Prices"], route_class=AutoDeriveResponsesAPIRoute)


@router.post("/search")
async def search_prices(payload: PriceSearchRequest) -> PriceSearchResponse:
    query = payload.query
    fixed_query: str | None = None
    if not payload.bypass_spellchecker:
        query = await asyncio.to_thread(spellcheck, payload.query)
        if query != payload.query:
            fixed_query = query

    yandex_result, wildberries_result, ozon_result = await asyncio.gather(
        parse_yandex_market_products(
            query,
            payload.limit,
            payload.skip,
            location=payload.location,
        ),
        parse_wildberries_products(
            query,
            payload.limit,
            payload.skip,
            location=payload.location,
        ),
        parse_ozon_products(
            query,
            payload.limit,
            payload.skip,
            location=payload.location,
        ),
        return_exceptions=True,
    )

    return PriceSearchResponse(
        query=payload.query,
        fixed_query=fixed_query,
        results=[
            _build_yandex_market_result(yandex_result),
            _build_wildberries_result(wildberries_result),
            _build_ozon_result(ozon_result),
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
            brand=_optional_brand(item.get("brand")),
            price=float(item["sale_price"]),
            original_price=_optional_float(item.get("original_price")),
            url=_optional_str(item.get("url")),
            image_url=_optional_str(item.get("image_url")),
        )
        for item in result
        if item.get("sale_price") is not None
    ]
    return MarketplacePriceResult(source=source, prices=prices)


def _build_ozon_result(result: list[dict] | BaseException) -> MarketplacePriceResult:
    source = "Ozon"
    if isinstance(result, BaseException):
        return MarketplacePriceResult(source=source, prices=[], error=str(result))

    prices = [
        ProductPrice(
            source=source,
            name=item.get("name"),
            brand=_optional_brand(item.get("brand")),
            price=_optional_float(item.get("sale_price")),
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
            brand=_optional_brand(item.get("brand")),
            price=float(item["sale_price"]),
            original_price=_optional_float(item.get("original_price")),
            url=_optional_str(item.get("url")),
            image_url=_optional_str(item.get("image_url")),
        )
        for item in result
        if item.get("sale_price") is not None
    ]
    return MarketplacePriceResult(source=source, prices=prices)


def _optional_brand(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() == "N/A":
        return None
    return text


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

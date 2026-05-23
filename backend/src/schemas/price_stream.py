from typing import Literal

from src.schemas.price import ProductPrice
from src.schemas.pydantic_base import BaseSchema


class PriceSearchMetaEvent(BaseSchema):
    type: Literal["meta"] = "meta"
    query: str
    fixed_query: str | None = None


class PriceSearchBatchEvent(BaseSchema):
    type: Literal["batch"] = "batch"
    source: str
    prices: list[ProductPrice]


class PriceSearchSourceDoneEvent(BaseSchema):
    type: Literal["source_done"] = "source_done"
    source: str
    error: str | None = None


class PriceSearchDoneEvent(BaseSchema):
    type: Literal["done"] = "done"
    query: str
    fixed_query: str | None = None

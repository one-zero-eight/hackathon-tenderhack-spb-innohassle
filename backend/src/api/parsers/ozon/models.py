from dataclasses import asdict, dataclass


@dataclass
class ProductResult:
    title: str
    url: str
    price: str | None
    image_url: str | None
    description: str | None
    position: int
    original_price: str | None = None
    brand: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

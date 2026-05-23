from dataclasses import asdict, dataclass


@dataclass
class ProductResult:
    title: str
    url: str
    price: str | None
    image_url: str | None
    description: str | None
    position: int

    def to_dict(self) -> dict:
        return asdict(self)

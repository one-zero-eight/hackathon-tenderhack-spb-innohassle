class OzonAccessError(Exception):
    """Ozon показал антибот, капчу или пустую выдачу."""

    def __init__(self, message: str, *, url: str | None = None) -> None:
        self.url = url
        super().__init__(message)

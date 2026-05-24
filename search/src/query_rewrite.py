FILTERS = "-yandex -ozon -wb -wildberries -market.yandex -avito -youla -aliexpress"
PREFIX = "купить онлайн"

def rewrite_query(query: str, region: str = "санкт-петербург") -> str:
    return f"{region} {PREFIX} {query.strip()} {FILTERS}"


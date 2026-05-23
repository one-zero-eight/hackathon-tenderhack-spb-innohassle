FILTERS = "-yandex -ozon -wb -wildberries -market.yandex -avito -youla -aliexpress"
PREFIX = "купить онлайн"


def rewrite_query(query: str, region: str = "санкт-петербург") -> str:
    return f"{region} {PREFIX} {query.strip()} {FILTERS}"


if __name__ == "__main__":
    while True:
        query = input("Enter a query: ")
        if query == "exit":
            break
        print(rewrite_query(query))

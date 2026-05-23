# Prices API — NDJSON stream

`POST /prices/search` возвращает поток **NDJSON** (`Content-Type: application/x-ndjson`): одна строка = один JSON-объект. Читайте ответ построчно, пока не придёт `"type": "done"`.

Локально (через прокси фронта): `POST /api/prices/search`  
Напрямую к API: `http://127.0.0.1:8000/prices/search` (порт зависит от деплоя).

Паттерн такой же, как у search-сервиса (`search/AGENTS.md`), но семантика событий другая: здесь **`batch` дописывает товары**, а не полный снимок как `page`.

---

## Запрос

```http
POST /prices/search
Content-Type: application/json
Accept: application/x-ndjson
```

```json
{
  "query": "наушники",
  "limit": 100,
  "skip": 0,
  "location": "Москва",
  "bypass_spellchecker": false
}
```

| Поле | По умолчанию | Описание |
|------|----------------|----------|
| `query` | — | Поисковая строка (обязательно, 1+ символ) |
| `limit` | `5` | Макс. товаров **с каждого** маркетплейса (1–100) |
| `skip` | `0` | Пропустить первые N позиций в выдаче каждого источника |
| `location` | Москва | Город/регион для WB, Yandex Market, Ozon |
| `bypass_spellchecker` | `false` | Не исправлять опечатки в `query` |

Парсеры **Yandex Market**, **Wildberries** и **Ozon** запускаются **параллельно**. События `batch` и `source_done` от разных источников могут идти вперемешку.

**Важно:** обычный клиент «один JSON в ответе» (OpenAPI `POST` + `response.json()`) **не подходит** — соединение держится открытым, данные приходят частями.

---

## Как читать поток (общее правило)

1. **`meta`** — один раз в начале (исходный запрос и опционально исправленный).
2. **`batch`** — много раз: порция товаров одного маркетплейса → **дописать** к списку этого `source`.
3. **`source_done`** — три раза (по одному на маркетплейс): источник закончил или упал с ошибкой.
4. **`done`** — один раз в конце: весь поиск завершён.

Между строками может быть долгая пауза — это нормально (парсинг, скролл, антибот). Не обрывайте запрос, пока не получили `done`.

При ошибке одного источника приходит `source_done` с `"error": "…"`; остальные источники продолжают работать.

---

## События

### `meta`

```json
{
  "type": "meta",
  "query": "наушнки",
  "fixed_query": "наушники"
}
```

| Поле | Описание |
|------|----------|
| `query` | Как ввёл пользователь |
| `fixed_query` | Исправленный запрос или `null`, если правка не нужна |

Поиск выполняется по исправленному тексту, если `fixed_query` не `null`.

### `batch`

```json
{
  "type": "batch",
  "source": "Wildberries",
  "prices": [
    {
      "source": "Wildberries",
      "name": "…",
      "brand": "…",
      "price": 1999.0,
      "original_price": 2499.0,
      "url": "https://…",
      "image_url": "https://…"
    }
  ]
}
```

| Поле | Описание |
|------|----------|
| `source` | `"Yandex Market"` \| `"Wildberries"` \| `"Ozon"` |
| `prices` | Массив `ProductPrice` (может быть пустым — такие `batch` не отправляются) |

**Правило для UI:** для каждого `source` делайте **append** к `prices`, не заменяйте весь ответ.

Товары без цены в сыром парсинге отбрасываются и в `batch` не попадают.

### `source_done`

```json
{
  "type": "source_done",
  "source": "Ozon",
  "error": null
}
```

При сбое: `"error": "текст исключения"`. Уже пришедшие `batch` для этого источника сохраняются.

### `done`

```json
{
  "type": "done",
  "query": "наушнки",
  "fixed_query": "наушники"
}
```

После `done` новых строк не будет.

---

## Типичная последовательность

```
meta
  → batch (Yandex Market) → batch (Wildberries) → …
  → source_done (Yandex Market)
  → batch (Ozon) → …
  → source_done (Wildberries)
  → source_done (Ozon)
done
```

Порядок `batch` / `source_done` **не гарантирован**, кроме того что `meta` первый, а `done` последний.

---

## Откуда берутся батчи (бэкенд)

| Источник | Когда шлётся `batch` |
|----------|----------------------|
| Yandex Market | после каждой страницы SERP (~8 товаров) |
| Wildberries | при догрузке карточек скроллом (~10 товаров) |
| Ozon | при прокрутке выдачи (~10 товаров) |

Реализация: `iter_yandex_market_products`, `iter_wildberries_products`, `iter_ozon_products` в `src/api/parsers/`.

---

## Схемы Pydantic (контракт)

События описаны в `src/schemas/price_stream.py`, тело запроса и `ProductPrice` — в `src/schemas/price.py`.

---

## Клиент на Python

```python
import json
import httpx

URL = "http://127.0.0.1:8000/prices/search"
body = {"query": "iphone", "limit": 20, "location": "Москва"}

by_source: dict[str, list[dict]] = {}

with httpx.stream("POST", URL, json=body, headers={"Accept": "application/x-ndjson"}, timeout=None) as resp:
    resp.raise_for_status()
    for line in resp.iter_lines():
        if not line:
            continue
        event = json.loads(line)
        t = event.get("type")

        if t == "meta":
            print("meta", event.get("fixed_query") or event["query"])
        elif t == "batch":
            by_source.setdefault(event["source"], []).extend(event["prices"])
            print("batch", event["source"], len(event["prices"]))
        elif t == "source_done":
            print("source_done", event["source"], event.get("error"))
        elif t == "done":
            print("done, total:", {k: len(v) for k, v in by_source.items()})
            break
```

---

## Клиент на TypeScript (для фронтенда)

Структура как у `@/api/search` (`events.ts` + `stream.ts` + `fetch` + `ReadableStream`), но обработчики другие.

1. **`fetch`**, не `openapi-fetch` / `eventsFetch.POST` для этого эндпоинта.
2. Заголовок `Accept: application/x-ndjson`.
3. Читать `response.body` через `getReader()` + `TextDecoder`, буфер до `\n`.
4. На каждый `batch` — merge по `source`.
5. `isLoading` — до `done`; при `AbortController` на unmount — игнорировать `AbortError`.

Псевдокод накопления (итог как старый `PriceSearchResponse`):

```ts
type MarketplaceRow = { source: string; prices: ProductPrice[]; error: string | null }

let state = { query: '', fixed_query: null as string | null, results: [] as MarketplaceRow[] }

function onBatch(event: { source: string; prices: ProductPrice[] }) {
  const row = state.results.find((r) => r.source === event.source)
  if (row) row.prices.push(...event.prices)
  else state.results.push({ source: event.source, prices: [...event.prices], error: null })
}

function onSourceDone(event: { source: string; error: string | null }) {
  if (!event.error) return
  const row = state.results.find((r) => r.source === event.source)
  if (row) row.error = event.error
  else state.results.push({ source: event.source, prices: [], error: event.error })
}
```

Для карточек на UI можно переиспользовать `mapPriceSearchResponse(state)` из `@/lib/mapSearchResults`.

Рекомендуемая раскладка модулей (аналог `frontend/src/api/search/`):

```
frontend/src/api/prices/
  events.ts   — типы meta | batch | source_done | done, type guard
  state.ts    — emptyResponse, applyEvent, clone
  stream.ts   — streamPriceSearch(params, handlers, signal)
  index.ts    — re-export
```

Хук `usePriceSearch`: `useEffect` + `streamPriceSearch` + `queryClient.setQueryData` на каждое обновление (как `useYandexSearchExtended` для search-стрима).

---

## Отладка curl

```bash
curl -N -X POST http://127.0.0.1:8000/prices/search \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/x-ndjson' \
  -d '{"query":"iphone","limit":20,"location":"Москва"}'
```

`-N` отключает буферизацию — строки видны сразу.

---

## Прокси / nginx

Ответ не буферизовать. Бэкенд отдаёт `X-Accel-Buffering: no`, `Cache-Control: no-cache`, `Connection: keep-alive`.

---

## Отличие от search API

| | Search (`/yandex_search`) | Prices (`/prices/search`) |
|--|---------------------------|---------------------------|
| Метод | GET | POST |
| Прогресс | `page` = **полный снимок**, заменить state | `batch` = **дельта**, append по `source` |
| Группировка | по `hostname` | по маркетплейсу (`source`) |
| Завершение источника | нет отдельного события | `source_done` на каждый из 3 парсеров |

Код стрима: `src/api/prices/routes.py` → `_price_search_stream`.

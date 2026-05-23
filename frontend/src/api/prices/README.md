# Price search stream (`POST /prices/search`)

Бэкенд отдаёт **NDJSON**: каждая строка — один JSON-объект. Обычный `openapi-fetch` / `eventsFetch.POST` здесь **не подходит** (ждёт один JSON в конце ответа).

Базовый URL: `VITE_API_URL` (по умолчанию `/api`).

## Запрос

```http
POST /api/prices/search
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
| `query` | — | Поисковая строка (обязательно) |
| `limit` | `5` | Сколько товаров с **каждого** маркетплейса (1–100) |
| `skip` | `0` | Пропуск первых N позиций |
| `location` | Москва | Город для региональных цен (WB / Yandex / Ozon) |
| `bypass_spellchecker` | `false` | Не исправлять опечатки в запросе |

Парсеры **Wildberries**, **Ozon** и **Yandex Market** работают **параллельно**; события от них могут приходить вперемешку.

## События (порядок не фиксирован, кроме `done` в конце)

### `meta` — один раз в начале

```json
{"type":"meta","query":"наушники","fixed_query":"наушники"}
```

`fixed_query` — исправленный запрос; `null`, если правка не нужна.

### `batch` — порция товаров (много раз)

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

`source`: `"Wildberries"` | `"Ozon"` | `"Yandex Market"`.

**Правило для UI:** для каждого `source` **дописывайте** `prices` к уже накопленному списку (append), а не заменяйте весь ответ целиком.

### `source_done` — маркетплейс закончил

```json
{"type":"source_done","source":"Ozon","error":null}
```

При ошибке: `"error": "текст"`, `prices` для этого источника могут быть пустыми или неполными.

### `done` — весь поиск завершён

```json
{"type":"done","query":"наушники","fixed_query":null}
```

После `done` новых строк не будет.

## Минимальный клиент (TypeScript)

Похожий разбор строк — в `@/api/search/stream.ts` (`readNdjsonStream`).

```ts
const API = import.meta.env.VITE_API_URL ?? '/api'

type Accumulated = {
  query: string
  fixed_query: string | null
  results: Array<{ source: string; prices: unknown[]; error: string | null }>
}

async function searchPricesStream(
  body: Record<string, unknown>,
  onUpdate: (state: Accumulated) => void,
  signal?: AbortSignal,
) {
  const res = await fetch(`${API}/prices/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/x-ndjson' },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)

  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const state: Accumulated = { query: String(body.query), fixed_query: null, results: [] }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let nl: number
    while ((nl = buffer.indexOf('\n')) !== -1) {
      const line = buffer.slice(0, nl).trim()
      buffer = buffer.slice(nl + 1)
      if (!line) continue

      const event = JSON.parse(line) as { type: string; source?: string; prices?: unknown[]; error?: string | null }

      if (event.type === 'meta') {
        state.query = (event as { query: string }).query
        state.fixed_query = (event as { fixed_query?: string | null }).fixed_query ?? null
      } else if (event.type === 'batch' && event.source && event.prices) {
        const row = state.results.find((r) => r.source === event.source)
        if (row) row.prices.push(...event.prices)
        else state.results.push({ source: event.source, prices: [...event.prices], error: null })
      } else if (event.type === 'source_done' && event.source) {
        const row = state.results.find((r) => r.source === event.source)
        if (row) row.error = event.error ?? null
        else state.results.push({ source: event.source, prices: [], error: event.error ?? null })
      } else if (event.type === 'done') {
        onUpdate(state)
        return state
      }
      onUpdate({ ...state, results: state.results.map((r) => ({ ...r, prices: [...r.prices] })) })
    }
  }
  return state
}
```

## Интеграция в React

1. В `useEffect` вызывать `searchPricesStream` с `AbortController` при смене `query` / `location`.
2. На каждый `onUpdate` класть снимок в `useState` или `queryClient.setQueryData(['price-search', …], snapshot)`.
3. Для UI использовать `mapPriceSearchResponse` из `@/lib/mapSearchResults` (тот же формат, что у старого `PriceSearchResponse`).
4. `isLoading` — `true` до события `done`; при `AbortError` на размонтировании ошибку не показывать.

Хук `usePriceSearch` сейчас ходит через `eventsFetch.POST` — его нужно перевести на стрим (или вынести логику в `stream.ts` + `events.ts` в этой папке).

## Отладка

```bash
curl -N -X POST http://localhost:8000/api/prices/search \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/x-ndjson' \
  -d '{"query":"iphone","limit":20,"location":"Москва"}'
```

Флаг `-N` отключает буферизацию — строки видны по мере парсинга.

## Прокси / nginx

Для стриминга нужен отключённый буфер ответа, например заголовок `X-Accel-Buffering: no` (бэкенд уже отдаёт его).

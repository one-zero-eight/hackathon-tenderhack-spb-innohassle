# Search stream API — frontend guide

How to consume the search service NDJSON stream from the frontend.

Each HTTP response line is one JSON object (`Content-Type: application/x-ndjson`). Read line-by-line until `"type": "done"`.

**Base URL:** `import.meta.env.VITE_SEARCH_API_URL ?? '/search-api'` (see `frontend/src/api/search/stream.ts`).

## Endpoints

| Path | Use |
|---|---|
| `GET /yandex_search?query=<text>&region=<text>` | Live search |
| `GET /yandex_search_mock?query=<text>&region=<text>` | Dev mock — same params (ignored), same event shape |

| Query param | Default | Meaning |
|---|---|---|
| `query` | required | User search text |
| `region` | `санкт-петербург` | City/region for Yandex |

## TypeScript types

```ts
export type SearchProduct = {
  title: string
  href: string
  price?: string | null
  thumbnail?: string | null
  description?: string
}

export type SearchSite = {
  hostname: string
  href?: string | null
  rating?: string | null
  reviews?: string | null
  delivery?: string | null
  favicon: string
  products: SearchProduct[]
}

export type SearchMetaEvent = {
  type: 'meta'
  query: string
  region: string
  rewritten_query: string
}

export type SearchDataEvent = {
  type: 'data'
  data: SearchSite[]
}

export type SearchDoneEvent = {
  type: 'done'
}

export type SearchStreamEvent = SearchMetaEvent | SearchDataEvent | SearchDoneEvent
```

## How to consume

**Replace the entire site list on every `data` event.** Do not merge or patch incrementally.

```ts
let sites: SearchSite[] = []

const response = await fetch(
  `${SEARCH_API_BASE}/yandex_search?` +
    new URLSearchParams({ query, region }),
)

const reader = response.body!.getReader()
const decoder = new TextDecoder()
let buffer = ''

while (true) {
  const { done, value } = await reader.read()
  if (done) break

  buffer += decoder.decode(value, { stream: true })

  while (true) {
    const newline = buffer.indexOf('\n')
    if (newline === -1) break

    const line = buffer.slice(0, newline).trim()
    buffer = buffer.slice(newline + 1)
    if (!line) continue

    const event = JSON.parse(line) as SearchStreamEvent

    if (event.type === 'meta') {
      // optional: show query / region in UI
    } else if (event.type === 'data') {
      sites = event.data // full replacement
    } else if (event.type === 'done') {
      break
    }
  }
}
```

**Silence between events is normal.** The server may take a long time between lines (shop discovery, favicon fetch, per-site searches). Keep the connection open until `"type": "done"`.

There is no `"type": "error"` event. On failure the stream may end early; keep whatever was in the last `data` snapshot.

## Event sequence

```
meta → data → data → … → done
```

| `data` event | What changed |
|---|---|
| 1st | Up to 3 shops discovered — metadata filled, `"products": []` |
| 2nd…Nth | One more shop got product offers after a site-scoped search |
| last | Shops with zero products after extraction are **removed** |

Example progression for `шина мишлейн`:

1. `meta`
2. `data` — 3 sites, all `"products": []`
3. `data` — first shop has offers
4. `data` — second shop has offers
5. `data` — third shop had no offers and is dropped; 2 sites remain
6. `done`

### First `data` snapshot (discovery)

```json
{
  "type": "data",
  "data": [
    {
      "hostname": "spb.koleso.ru",
      "href": "https://spb.koleso.ru/catalog/tyres/michelin/",
      "rating": "4,7",
      "reviews": "14,2K отзывов",
      "delivery": "Из магазина",
      "favicon": "https://spb.koleso.ru/favicon.ico",
      "products": []
    },
    {
      "hostname": "spb.shinservice.ru",
      "href": "https://spb.shinservice.ru/catalog/tyres/brand-is-michelin/",
      "rating": "4,6",
      "reviews": "12,9K отзывов",
      "delivery": "Курьер",
      "favicon": "https://spb.shinservice.ru/media/favicon/favicon-32x32.png",
      "products": []
    }
  ]
}
```

### Final `data` snapshot (with products)

```json
{
  "type": "data",
  "data": [
    {
      "hostname": "spb.koleso.ru",
      "href": "https://spb.koleso.ru/catalog/tyres/michelin/",
      "rating": "4,7",
      "reviews": "14,2K отзывов",
      "delivery": "Из магазина",
      "favicon": "https://spb.koleso.ru/favicon.ico",
      "products": [
        {
          "title": "Летняя шина Michelin Primacy 5 225/55 R18 98V",
          "href": "https://spb.koleso.ru/catalog/tyres/michelin/primacy-5/.../",
          "price": "24 440 ₽",
          "thumbnail": "//avatars.mds.yandex.net/get-goods_pic/10533023/.../square_166",
          "description": "Michelin Primacy 5 — премиальная летняя шина..."
        }
      ]
    }
  ]
}
```

### `meta`

```json
{
  "type": "meta",
  "query": "докторский халат",
  "region": "санкт-петербург",
  "rewritten_query": "санкт-петербург купить онлайн докторский халат -yandex -ozon ..."
}
```

No sites or products. Do not render results from this event.

### `done`

```json
{ "type": "done" }
```

Stream finished. The last `data` snapshot is the final UI state.

## Field reference

### Site

| Field | Type | UI notes |
|---|---|---|
| `hostname` | string | Display name / slug source |
| `href` | string \| null | Link to shop page on Yandex |
| `rating` | string \| null | Comma decimal, e.g. `"4,8"` — parse with `.replace(',', '.')` |
| `reviews` | string \| null | Label text, e.g. `"23,9K отзывов"` |
| `delivery` | string \| null | e.g. `"Курьер"`, `"Из аптеки"` |
| `favicon` | string | Use as `<img src>` for shop icon |
| `products` | array | Empty until that shop's offers are fetched |

### Product

| Field | Type | UI notes |
|---|---|---|
| `title` | string | Product name |
| `href` | string | Product page URL |
| `price` | string \| null | Display as-is, e.g. `"209 ₽"` |
| `thumbnail` | string \| null | Often protocol-relative (`//…`) — prefix `https:` |
| `description` | string | Optional snippet; may be omitted |

## UI helpers

**Thumbnail URLs** — normalize before use:

```ts
function normalizeProductImageUrl(url: string | null | undefined): string | null {
  if (!url?.trim()) return null
  if (url.startsWith('//')) return `https:${url}`
  return url
}
```

See `frontend/src/lib/normalizeProductImageUrl.ts` for Yandex avatar edge cases.

**Price parsing** — strip non-digits for sorting/comparison:

```ts
function parsePriceText(value: string | null | undefined): number | null {
  if (!value) return null
  const digits = value.replace(/[^\d]/g, '')
  return digits ? Number.parseInt(digits, 10) : null
}
```

**Rating parsing:**

```ts
function parseRatingText(value: string | null | undefined): number | null {
  if (!value) return null
  const parsed = Number.parseFloat(value.replace(',', '.').trim())
  return Number.isFinite(parsed) ? parsed : null
}
```

**Counts from a snapshot:**

```ts
const siteCount = event.data.length
const productCount = event.data.reduce((n, site) => n + site.products.length, 0)
```

**Loading state** — show loading from first byte until `done`. Optionally show partial results on each `data` event (shops appear first, products fill in per shop).

**Throttling** — rapid `data` events can be batched before `setState` (see `STREAM_UI_THROTTLE_MS` in `frontend/src/hooks/useYandexSearchExtended.ts`).

## Mock endpoint (local dev)

Call `/yandex_search_mock` with any `query` / `region`. Response shape is identical to live `/yandex_search` — use the same parser and UI code.

## Common mistakes

| Mistake | Correct approach |
|---|---|
| Appending products on each `data` event | Replace entire `data` array |
| Treating silence as failure | Keep reading until `"type": "done"` |
| Rendering from `meta` | Only `data` events carry sites/products |
| Expecting empty shops in the final snapshot | Shops with zero products are removed after extraction |
| Using `thumbnail` as-is when it starts with `//` | Prefix `https:` |
| Parsing `rating` with `.` decimal | API uses comma decimal (`"4,8"`) |

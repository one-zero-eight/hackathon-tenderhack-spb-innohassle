# Search API — streaming guide for AI agents

The search service exposes two **NDJSON stream** endpoints. Each line is one JSON object. Read the response line-by-line until you see `"type": "done"`.

Default base URL (local): `http://127.0.0.1:9005`

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /yandex_search?query=<text>&region=<text>` | Yandex search only. Products come from SERP snippets. |
| `GET /yandex_search_extended?query=<text>&region=<text>` | Yandex search **in parallel** with page extraction (HTTP fetch + LLM). Products start as SERP snippets, then get replaced/enriched after page parsing. |

Both return `Content-Type: application/x-ndjson`.

| Query param | Default | Meaning |
|---|---|---|
| `query` | required | User search text |
| `region` | `санкт-петербург` | Prepended to the Yandex query (city/region) |

## How to consume the stream

**Rule: treat every `page` event as a full snapshot. Replace your entire UI/state with the new data. Do not merge or patch incrementally.**

```python
state = None

for line in response.iter_lines():
    event = json.loads(line)

    if event["type"] == "meta":
        # optional: store query metadata
        pass

    elif event["type"] == "page":
        state = event["results"]  # <-- replace, do not append

    elif event["type"] == "done":
        break
```

**The stream may go silent for a long time between events.** No new lines does not mean the request failed — the server may still be working. Keep the connection open and keep reading until `"type": "done"`.

There is no `"type": "error"` event. On failure the stream stops at `"done"` with whatever was collected in the last `page` snapshot.

## Event sequence

### Always

1. **`meta`** — once, at the start
2. **`page`** — zero or more times; each contains the **complete** current result set
3. **`done`** — once, at the end

### `/yandex_search`

```
meta → page → page → … → done
```

A new `page` is emitted after each Yandex SERP page is scraped (up to 4 pages: first + 3 pager links).

### `/yandex_search_extended`

```
meta → page → page → page → … → done
```

`page` events are emitted on **every** state change:

- new Yandex SERP results arrived (`extracted: false` products added)
- a product finished extraction (`extracted: false` row removed, one or more `extracted: true` rows added)

The stream ends when Yandex search is finished **and** all in-flight extractions are finished.

---

## Event schemas

### `meta`

```json
{
  "type": "meta",
  "query": "айфон 17",
  "region": "санкт-петербург",
  "rewritten_query": "санкт-петербург купить онлайн айфон 17 -yandex -ozon ..."
}
```

| Field | Meaning |
|---|---|
| `query` | Original user query |
| `region` | Region passed to the API |
| `rewritten_query` | Query sent to Yandex (region + filters applied) |

No product data yet. Do not render results from this event.

---

### `page`

```json
{
  "type": "page",
  "results": [
    {
      "hostname": "example.ru",
      "products": [ /* ... */ ]
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `results` | **Full** list of hostname groups. Replace previous state entirely. |

#### `results[]` shape

```json
{
  "hostname": "store.example.ru",
  "products": [ /* product objects */ ]
}
```

- Sorted alphabetically by `hostname`.
- One Yandex listing with the same `href` appears at most once as `extracted: false`.
- After extraction, the `extracted: false` row for that `href` is **removed** and replaced by one or more `extracted: true` rows.

---

### Product objects

#### Not yet extracted (`extracted: false`)

Yandex SERP snippet. Present in both endpoints; in `/yandex_search` all products look like this.

```json
{
  "extracted": false,
  "title": "Apple iPhone 17 256GB",
  "hostname": "store.example.ru",
  "href": "https://store.example.ru/product/123",
  "rating": "4.8",
  "reviews": "128",
  "delivery": "Завтра",
  "price": "89 990 ₽",
  "thumbnail": "https://..."
}
```

Fields may be `null` if absent on the SERP.

#### Extracted (`extracted: true`)

Present only after `/yandex_search_extended` finishes parsing the product page. One Yandex result can become **multiple** extracted products (e.g. several offers on one page; max 5 per page).

```json
{
  "extracted": true,
  "hostname": "store.example.ru",
  "href": "https://store.example.ru/product/123",
  "name": "Apple iPhone 17 256GB",
  "cost": "89 990 ₽",
  "description": "…",
  "characteristics": {
    "Память": "256 ГБ",
    "Цвет": "белый"
  }
}
```

If extraction finds nothing, a single stub row is kept with `extracted: true` and the original Yandex fields (`title`, `price`, etc.).

---

### `done`

```json
{
  "type": "done"
}
```

Stream finished. Keep the last `page` snapshot as final state.

---

## Counts helpers

From a `page.results` snapshot:

```python
hostnames = len(results)
products = sum(len(g["products"]) for g in results)
extracted = sum(1 for g in results for p in g["products"] if p.get("extracted"))
non_extracted = products - extracted
```

---

## Example: httpx

```python
import httpx, json

with httpx.stream(
    "GET",
    "http://127.0.0.1:9005/yandex_search_extended",
    params={"query": "айфон 17", "region": "санкт-петербург"},
    timeout=None,
) as response:
    response.raise_for_status()
    for line in response.iter_lines():
        event = json.loads(line)
        if event["type"] == "page":
            results = event["results"]  # full replacement
        elif event["type"] == "done":
            break
```

CLI client: `uv run python client.py "айфон 17" --extended` (from `search/src/`).

---

## Common mistakes

| Mistake | Correct approach |
|---|---|
| Appending new products from each `page` event | Replace entire `results` array |
| Treating silence as failure | Keep reading until `"type": "done"` |
| Treating `meta` as having products | Only `page` events carry `results` |
| Assuming 1 Yandex row → 1 final product | Extended mode may expand one row into several `extracted: true` products |

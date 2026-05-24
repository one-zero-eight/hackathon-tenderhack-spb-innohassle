/** NDJSON stream events — /yandex_search */

export type SearchProductItem = {
  title: string | null
  href: string | null
  price?: string | null
  thumbnail?: string | null
  description?: string | null
}

export type SearchShop = {
  hostname: string
  href: string | null
  rating?: string | null
  reviews?: string | null
  delivery?: string | null
  products: SearchProductItem[]
  favicon?: string | null
}

export type SearchMetaEvent = {
  type: 'meta'
  query: string
  region: string
  rewritten_query: string
}

export type SearchDataEvent = {
  type: 'data'
  data: SearchShop[]
}

export type SearchDoneEvent = {
  type: 'done'
}

export type SearchStreamEvent = SearchMetaEvent | SearchDataEvent | SearchDoneEvent

export function isSearchStreamEvent(value: unknown): value is SearchStreamEvent {
  if (!value || typeof value !== 'object' || !('type' in value)) return false
  const type = (value as { type: unknown }).type
  return type === 'meta' || type === 'data' || type === 'done'
}

/** NDJSON stream events — see search/AGENTS.md */

export type SearchProductSnippet = {
  extracted: false
  title: string | null
  hostname: string
  href: string | null
  rating?: string | null
  reviews?: string | null
  delivery?: string | null
  price?: string | null
  thumbnail?: string | null
}

export type SearchProductExtracted = {
  extracted: true
  hostname: string
  href: string | null
  name?: string | null
  cost?: string | null
  description?: string | null
  characteristics?: Record<string, string> | null
  title?: string | null
  price?: string | null
  thumbnail?: string | null
}

export type SearchStreamProduct = SearchProductSnippet | SearchProductExtracted

export type SearchHostnameGroup = {
  hostname: string
  products: SearchStreamProduct[]
}

export type SearchMetaEvent = {
  type: 'meta'
  query: string
  region: string
  rewritten_query: string
}

export type SearchPageEvent = {
  type: 'page'
  results: SearchHostnameGroup[]
}

export type SearchDoneEvent = {
  type: 'done'
}

export type SearchStreamEvent = SearchMetaEvent | SearchPageEvent | SearchDoneEvent

export function isSearchStreamEvent(value: unknown): value is SearchStreamEvent {
  if (!value || typeof value !== 'object' || !('type' in value)) return false
  const type = (value as { type: unknown }).type
  return type === 'meta' || type === 'page' || type === 'done'
}

/** NDJSON stream events — see backend/src/api/prices/README.md */

export type ProductPrice = {
  source: string
  price?: number | null
  name?: string | null
  brand?: string | null
  original_price?: number | null
  url?: string | null
  image_url?: string | null
}

export type PriceSearchMetaEvent = {
  type: 'meta'
  query: string
  fixed_query?: string | null
}

export type PriceSearchBatchEvent = {
  type: 'batch'
  source: string
  prices: ProductPrice[]
}

export type PriceSearchSourceDoneEvent = {
  type: 'source_done'
  source: string
  error?: string | null
}

export type PriceSearchDoneEvent = {
  type: 'done'
  query: string
  fixed_query?: string | null
}

export type PriceStreamEvent = PriceSearchMetaEvent | PriceSearchBatchEvent | PriceSearchSourceDoneEvent | PriceSearchDoneEvent

export function isPriceStreamEvent(value: unknown): value is PriceStreamEvent {
  if (!value || typeof value !== 'object' || !('type' in value)) return false
  const type = (value as { type: unknown }).type
  return type === 'meta' || type === 'batch' || type === 'source_done' || type === 'done'
}

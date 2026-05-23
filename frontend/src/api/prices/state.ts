import type { PriceStreamEvent, ProductPrice } from './events'

export type MarketplacePriceResult = {
  source: string
  prices: ProductPrice[]
  error?: string | null
  complete?: boolean
}

export type PriceSearchStreamState = {
  query: string
  fixed_query: string | null
  results: MarketplacePriceResult[]
}

export function emptyPriceSearchResponse(query: string): PriceSearchStreamState {
  return { query, fixed_query: null, results: [] }
}

export function applyPriceSearchEvent(state: PriceSearchStreamState, event: PriceStreamEvent): PriceSearchStreamState {
  switch (event.type) {
    case 'meta':
      return { ...state, query: event.query, fixed_query: event.fixed_query ?? null }
    case 'batch': {
      const index = state.results.findIndex((item) => item.source === event.source)
      if (index >= 0) {
        const row = state.results[index]!
        const updatedRow: MarketplacePriceResult = {
          ...row,
          prices: [...row.prices, ...event.prices],
        }
        const results = state.results.slice()
        results[index] = updatedRow
        return { ...state, results }
      }
      return {
        ...state,
        results: [...state.results, { source: event.source, prices: [...event.prices], error: null }],
      }
    }
    case 'source_done': {
      const index = state.results.findIndex((item) => item.source === event.source)
      if (index >= 0) {
        const results = state.results.slice()
        results[index] = {
          ...results[index]!,
          complete: true,
          error: event.error ?? results[index]!.error,
        }
        return { ...state, results }
      }
      return {
        ...state,
        results: [...state.results, { source: event.source, prices: [], error: event.error ?? null, complete: true }],
      }
    }
    case 'done':
      return {
        ...state,
        query: event.query,
        fixed_query: event.fixed_query ?? null,
        results: state.results.map((row) => ({ ...row, complete: true })),
      }
  }
}

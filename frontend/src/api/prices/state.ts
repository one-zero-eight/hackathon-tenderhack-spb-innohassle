import type { PriceStreamEvent, ProductPrice } from './events'

export type MarketplacePriceResult = {
  source: string
  prices: ProductPrice[]
  error?: string | null
}

export type PriceSearchStreamState = {
  query: string
  fixed_query: string | null
  results: MarketplacePriceResult[]
}

export function emptyPriceSearchResponse(query: string): PriceSearchStreamState {
  return { query, fixed_query: null, results: [] }
}

export function clonePriceSearchState(state: PriceSearchStreamState): PriceSearchStreamState {
  return {
    query: state.query,
    fixed_query: state.fixed_query,
    results: state.results.map((row) => ({ ...row, prices: [...row.prices] })),
  }
}

export function applyPriceSearchEvent(state: PriceSearchStreamState, event: PriceStreamEvent): PriceSearchStreamState {
  const next = clonePriceSearchState(state)

  switch (event.type) {
    case 'meta':
      next.query = event.query
      next.fixed_query = event.fixed_query ?? null
      break
    case 'batch': {
      const row = next.results.find((item) => item.source === event.source)
      if (row) row.prices.push(...event.prices)
      else next.results.push({ source: event.source, prices: [...event.prices], error: null })
      break
    }
    case 'source_done': {
      if (!event.error) break
      const row = next.results.find((item) => item.source === event.source)
      if (row) row.error = event.error
      else next.results.push({ source: event.source, prices: [], error: event.error })
      break
    }
    case 'done':
      next.query = event.query
      next.fixed_query = event.fixed_query ?? null
      break
  }

  return next
}

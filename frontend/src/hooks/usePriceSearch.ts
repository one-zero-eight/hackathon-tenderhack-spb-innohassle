import { emptyPriceSearchResponse, streamPriceSearch, type PriceSearchStreamState } from '@/api/prices'
import { mapPriceSearchResponse } from '@/lib/mapSearchResults'
import type { SiteResult } from '@/lib/searchResults'
import { useQuery, useQueryClient, type QueryClient, type QueryKey } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

export const PRICE_SEARCH_LIMIT = 100
export const PRICE_SEARCH_STALE_MS = 5 * 60 * 1000

export type PriceSearchParams = {
  query: string
  location?: string | null
  limit?: number
  skip?: number
  bypassSpellchecker?: boolean
}

export type PriceSearchData = {
  sites: SiteResult[]
  fixedQuery: string | null
  effectiveQuery: string
}

export function priceSearchQueryKey({ query, location, limit = PRICE_SEARCH_LIMIT, skip = 0, bypassSpellchecker = false }: PriceSearchParams) {
  return ['price-search', query.trim(), location ?? '', limit, skip, bypassSpellchecker] as const
}

function mapPriceSearchData(data: PriceSearchStreamState): PriceSearchData {
  const fixedQuery = data.fixed_query?.trim() || null
  return {
    sites: mapPriceSearchResponse(data),
    fixedQuery,
    effectiveQuery: fixedQuery ?? data.query,
  }
}

function queryKeyId(queryKey: QueryKey): string {
  return JSON.stringify(queryKey)
}

type StreamEntry = {
  controller: AbortController
  promise: Promise<PriceSearchStreamState>
  refs: number
}

const activeStreams = new Map<string, StreamEntry>()
const completedStreams = new Set<string>()

function acquirePriceSearchStream(params: PriceSearchParams, queryClient: QueryClient): { promise: Promise<PriceSearchStreamState>; release: () => void } {
  const queryKey = priceSearchQueryKey(params)
  const key = queryKeyId(queryKey)
  completedStreams.delete(key)
  const existing = activeStreams.get(key)

  if (existing) {
    existing.refs += 1
    return {
      promise: existing.promise,
      release: () => {
        existing.refs -= 1
        if (existing.refs <= 0) {
          existing.controller.abort()
          activeStreams.delete(key)
        }
      },
    }
  }

  const controller = new AbortController()
  const initialState = emptyPriceSearchResponse(params.query.trim())
  queryClient.setQueryData(queryKey, initialState)

  const promise = streamPriceSearch(
    params,
    {
      onState: (state) => {
        queryClient.setQueryData(queryKey, state)
      },
    },
    controller.signal,
  )
    .then((final) => {
      completedStreams.add(key)
      return final
    })
    .finally(() => {
    const entry = activeStreams.get(key)
    if (entry?.controller === controller) {
      activeStreams.delete(key)
    }
  })

  activeStreams.set(key, { controller, promise, refs: 1 })

  return {
    promise: promise,
    release: () => {
      const entry = activeStreams.get(key)
      if (!entry) return
      entry.refs -= 1
      if (entry.refs <= 0) {
        entry.controller.abort()
        activeStreams.delete(key)
      }
    },
  }
}

export function findSiteInPriceSearchCache(queryClient: QueryClient, siteSlug: string, location?: string | null): SiteResult | undefined {
  const normalizedLocation = location ?? ''
  const entries = queryClient.getQueriesData<PriceSearchStreamState>({ queryKey: ['price-search'] })

  for (const [queryKey, data] of entries) {
    if (!data) continue
    if (queryKey[2] !== normalizedLocation) continue
    const site = mapPriceSearchData(data).sites.find((item) => item.slug === siteSlug)
    if (site) return site
  }

  return undefined
}

export function findProductInPriceSearchCache(queryClient: QueryClient, siteSlug: string, productId: string, location?: string | null) {
  const site = findSiteInPriceSearchCache(queryClient, siteSlug, location)
  if (!site) return null
  const product = site.products.find((item) => item.id === productId)
  if (!product) return null
  return { site, product }
}

export async function fetchPriceSearch(params: PriceSearchParams, signal?: AbortSignal): Promise<PriceSearchStreamState> {
  return streamPriceSearch(params, {}, signal)
}

function isFreshPriceSearchCache(queryClient: QueryClient, queryKey: ReturnType<typeof priceSearchQueryKey>): boolean {
  const key = queryKeyId(queryKey)
  if (!completedStreams.has(key)) return false
  const data = queryClient.getQueryData<PriceSearchStreamState>(queryKey)
  const updatedAt = queryClient.getQueryState(queryKey)?.dataUpdatedAt ?? 0
  return Boolean(data) && Date.now() - updatedAt < PRICE_SEARCH_STALE_MS
}

export function usePriceSearch(params: PriceSearchParams, enabled = true) {
  const queryClient = useQueryClient()
  const trimmed = params.query.trim()
  const active = enabled && trimmed.length > 0
  const queryKey = priceSearchQueryKey(params)
  const location = params.location ?? ''
  const limit = params.limit ?? PRICE_SEARCH_LIMIT
  const skip = params.skip ?? 0
  const bypassSpellchecker = params.bypassSpellchecker ?? false
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    const streamParams: PriceSearchParams = { query: trimmed, location, limit, skip, bypassSpellchecker }
    const streamQueryKey = priceSearchQueryKey(streamParams)

    if (!active) {
      return
    }

    if (isFreshPriceSearchCache(queryClient, streamQueryKey)) {
      return
    }

    let cancelled = false
    const { promise, release } = acquirePriceSearchStream(streamParams, queryClient)

    void Promise.resolve().then(() => {
      if (cancelled) return
      setStreaming(true)
      setError(null)
    })

    void promise
      .then(() => {
        if (cancelled) return
        setStreaming(false)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof DOMException && err.name === 'AbortError') return
        setError(err)
        setStreaming(false)
      })

    return () => {
      cancelled = true
      release()
    }
  }, [active, bypassSpellchecker, limit, location, queryClient, skip, trimmed])

  const query = useQuery({
    queryKey,
    queryFn: () => Promise.reject(new Error('Price search stream is managed manually')),
    enabled: false,
    staleTime: PRICE_SEARCH_STALE_MS,
    select: mapPriceSearchData,
  })

  return {
    ...query,
    data: query.data,
    isLoading: active && streaming,
    isFetching: active && streaming,
    isError: error != null,
    error: error ?? query.error,
  }
}

export function useSiteFromSearch(siteSlug: string, params: PriceSearchParams): SiteResult | undefined {
  const queryClient = useQueryClient()
  const trimmed = params.query.trim()
  if (!trimmed) return findSiteInPriceSearchCache(queryClient, siteSlug, params.location)

  const data = queryClient.getQueryData<PriceSearchStreamState>(priceSearchQueryKey(params))
  if (data) {
    return mapPriceSearchData(data).sites.find((site) => site.slug === siteSlug)
  }

  return findSiteInPriceSearchCache(queryClient, siteSlug, params.location)
}

export function useProductFromSearch(siteSlug: string, productId: string, params: PriceSearchParams) {
  const queryClient = useQueryClient()
  const site = useSiteFromSearch(siteSlug, params)
  const cached = findProductInPriceSearchCache(queryClient, siteSlug, productId, params.location)
  if (cached) return cached
  if (!site) return null
  const product = site.products.find((item) => item.id === productId)
  if (!product) return null
  return { site, product }
}

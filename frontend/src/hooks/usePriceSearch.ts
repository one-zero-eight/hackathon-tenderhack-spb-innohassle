import { emptyPriceSearchResponse, streamPriceSearch, type PriceSearchStreamState } from '@/api/prices'
import { type PriceSearchData } from '@/lib/mapSearchResults'
import { createPriceSearchMapper } from '@/lib/priceSearchMapper'
import type { SiteResult } from '@/lib/searchResults'
import { useQuery, useQueryClient, type QueryClient, type QueryKey } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

export const PRICE_SEARCH_LIMIT = 50
export const PRICE_SEARCH_STALE_MS = 5 * 60 * 1000
const STREAM_UI_THROTTLE_MS = 250
const COMPLETED_STREAMS_MAX = 32

export type PriceSearchParams = {
  query: string
  location?: string | null
  limit?: number
  skip?: number
  bypassSpellchecker?: boolean
  bypassRelevanceFilter?: boolean
}

export type { PriceSearchData }

function queryKeyId(queryKey: QueryKey): string {
  return JSON.stringify(queryKey)
}

type StreamEntry = {
  controller: AbortController
  promise: Promise<PriceSearchStreamState>
  refs: number
  throttler: QueryDataThrottler
}

const activeStreams = new Map<string, StreamEntry>()
const completedStreams = new Set<string>()

type QueryDataThrottler = {
  push: (data: PriceSearchData) => void
  flush: (data: PriceSearchData) => void
  cancel: () => void
}

function createQueryDataThrottler(queryClient: QueryClient, queryKey: QueryKey): QueryDataThrottler {
  let pending: PriceSearchData | null = null
  let timer: ReturnType<typeof setTimeout> | null = null

  const flushPending = () => {
    timer = null
    if (pending) {
      queryClient.setQueryData(queryKey, pending)
      pending = null
    }
  }

  return {
    push(data) {
      pending = data
      if (!timer) timer = setTimeout(flushPending, STREAM_UI_THROTTLE_MS)
    },
    flush(data) {
      if (timer) clearTimeout(timer)
      timer = null
      pending = null
      queryClient.setQueryData(queryKey, data)
    },
    cancel() {
      if (timer) clearTimeout(timer)
      timer = null
      pending = null
    },
  }
}

function markStreamCompleted(key: string) {
  completedStreams.add(key)
  if (completedStreams.size > COMPLETED_STREAMS_MAX) {
    const oldest = completedStreams.values().next().value
    if (oldest) completedStreams.delete(oldest)
  }
}

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
          existing.throttler.cancel()
          existing.controller.abort()
          activeStreams.delete(key)
        }
      },
    }
  }

  const controller = new AbortController()
  const throttler = createQueryDataThrottler(queryClient, queryKey)
  const mapper = createPriceSearchMapper()
  const cached = queryClient.getQueryData<PriceSearchData>(queryKey)
  if (!cached) {
    const initialState = emptyPriceSearchResponse(params.query.trim())
    throttler.flush(mapper.update(initialState))
  }

  const promise = streamPriceSearch(
    params,
    {
      onState: (state) => {
        throttler.push(mapper.update(state))
      },
    },
    controller.signal,
  )
    .then((final) => {
      throttler.flush(mapper.update(final))
      markStreamCompleted(key)
      return final
    })
    .finally(() => {
      const entry = activeStreams.get(key)
      if (entry?.controller === controller) {
        entry.throttler.cancel()
        activeStreams.delete(key)
      }
    })

  activeStreams.set(key, { controller, promise, refs: 1, throttler })

  return {
    promise,
    release: () => {
      const entry = activeStreams.get(key)
      if (!entry) return
      entry.refs -= 1
      if (entry.refs <= 0) {
        entry.throttler.cancel()
        entry.controller.abort()
        activeStreams.delete(key)
      }
    },
  }
}

export function priceSearchQueryKey({ query, location, limit = PRICE_SEARCH_LIMIT, skip = 0, bypassSpellchecker = false, bypassRelevanceFilter = true }: PriceSearchParams) {
  return ['price-search', query.trim(), location ?? '', limit, skip, bypassSpellchecker, bypassRelevanceFilter] as const
}

export function findSiteInPriceSearchCache(queryClient: QueryClient, siteSlug: string, query: string, location?: string | null): SiteResult | undefined {
  const data = queryClient.getQueryData<PriceSearchData>(priceSearchQueryKey({ query, location }))
  return data?.sites.find((item) => item.slug === siteSlug)
}

export function findProductInPriceSearchCache(queryClient: QueryClient, siteSlug: string, productId: string, query: string, location?: string | null) {
  const site = findSiteInPriceSearchCache(queryClient, siteSlug, query, location)
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
  const data = queryClient.getQueryData<PriceSearchData>(queryKey)
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
    const streamParams: PriceSearchParams = {
      query: trimmed,
      location,
      limit,
      skip,
      bypassSpellchecker,
      bypassRelevanceFilter: params.bypassRelevanceFilter ?? true,
    }
    const streamQueryKey = priceSearchQueryKey(streamParams)
    const streamKey = queryKeyId(streamQueryKey)
    const client = queryClient

    if (!active) return

    if (isFreshPriceSearchCache(client, streamQueryKey)) {
      return
    }

    const existing = activeStreams.get(streamKey)
    if (existing) {
      existing.refs += 1
      let cancelled = false
      void Promise.resolve().then(() => {
        if (!cancelled) setStreaming(true)
      })
      void existing.promise.finally(() => {
        if (!cancelled) setStreaming(false)
      })
      return () => {
        cancelled = true
        existing.refs -= 1
        if (existing.refs <= 0) {
          existing.throttler.cancel()
          existing.controller.abort()
          activeStreams.delete(streamKey)
        }
      }
    }

    let cancelled = false
    const { promise, release } = acquirePriceSearchStream(streamParams, client)

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
  }, [active, bypassSpellchecker, limit, location, params.bypassRelevanceFilter, queryClient, skip, trimmed])

  const query = useQuery({
    queryKey,
    queryFn: () => Promise.reject(new Error('Price search stream is managed manually')),
    enabled: false,
    staleTime: PRICE_SEARCH_STALE_MS,
    gcTime: PRICE_SEARCH_STALE_MS,
  })

  return {
    ...query,
    data: query.data as PriceSearchData | undefined,
    isLoading: active && streaming,
    isFetching: active && streaming,
    isError: error != null,
    error: error ?? query.error,
  }
}

export function useSiteFromSearch(siteSlug: string, params: PriceSearchParams): SiteResult | undefined {
  const queryClient = useQueryClient()
  return findSiteInPriceSearchCache(queryClient, siteSlug, params.query, params.location)
}

export function useProductFromSearch(siteSlug: string, productId: string, params: PriceSearchParams) {
  const queryClient = useQueryClient()
  const site = useSiteFromSearch(siteSlug, params)
  const cached = findProductInPriceSearchCache(queryClient, siteSlug, productId, params.query, params.location)
  if (cached) return cached
  if (!site) return null
  const product = site.products.find((item) => item.id === productId)
  if (!product) return null
  return { site, product }
}

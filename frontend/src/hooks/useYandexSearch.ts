import { streamYandexSearch, type SearchMetaEvent } from '@/api/search'
import { mapStreamSearchResults } from '@/lib/mapStreamSearchResults'
import type { SiteResult } from '@/lib/searchResults'
import { useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

const STREAM_UI_THROTTLE_MS = 250
export const YANDEX_SEARCH_STALE_MS = 5 * 60 * 1000

export type YandexSearchData = {
  sites: SiteResult[]
  meta: SearchMetaEvent | null
  complete?: boolean
}

const emptyYandexSearch = (): YandexSearchData => ({ sites: [], meta: null })

function normalizeRegion(region: string): string {
  return region.trim().toLowerCase()
}

export function yandexSearchQueryKey(query: string, region: string) {
  return ['yandex-search', query.trim(), normalizeRegion(region)] as const
}

function streamKeyId(queryKey: ReturnType<typeof yandexSearchQueryKey>): string {
  return JSON.stringify(queryKey)
}

const activeYandexStreams = new Map<
  string,
  {
    controller: AbortController
    promise: Promise<void>
    refs: number
    flush: () => void
    cancelThrottle: () => void
  }
>()
const completedYandexStreams = new Set<string>()

function markYandexStreamCompleted(key: string) {
  completedYandexStreams.add(key)
  if (completedYandexStreams.size > 32) {
    const oldest = completedYandexStreams.values().next().value
    if (oldest) completedYandexStreams.delete(oldest)
  }
}

export function getYandexSearchCache(queryClient: QueryClient, query: string, region: string): YandexSearchData | undefined {
  const trimmed = query.trim()
  const exact = queryClient.getQueryData<YandexSearchData>(yandexSearchQueryKey(trimmed, region))
  if (exact?.complete) return exact

  const entries = queryClient.getQueriesData<YandexSearchData>({ queryKey: ['yandex-search', trimmed] })
  for (const [, data] of entries) {
    if (data?.complete) return data
  }

  return exact
}

function isFreshYandexCache(queryClient: QueryClient, trimmed: string, region: string): boolean {
  const cacheKey = yandexSearchQueryKey(trimmed, region)
  const key = streamKeyId(cacheKey)
  if (!completedYandexStreams.has(key)) return false
  const data = getYandexSearchCache(queryClient, trimmed, region)
  return data?.complete === true
}

export function findSiteInYandexSearchCache(queryClient: QueryClient, siteSlug: string, query: string, region: string): SiteResult | undefined {
  const data = getYandexSearchCache(queryClient, query, region)
  return data?.sites.find((site) => site.slug === siteSlug)
}

function acquireYandexSearchStream(
  queryClient: QueryClient,
  trimmed: string,
  region: string,
): { promise: Promise<void>; release: () => void } {
  const cacheKey = yandexSearchQueryKey(trimmed, region)
  const key = streamKeyId(cacheKey)
  completedYandexStreams.delete(key)

  const existing = activeYandexStreams.get(key)
  if (existing) {
    existing.refs += 1
    return {
      promise: existing.promise,
      release: () => {
        existing.refs -= 1
        if (existing.refs <= 0) {
          existing.cancelThrottle()
          existing.controller.abort()
          activeYandexStreams.delete(key)
        }
      },
    }
  }

  const controller = new AbortController()
  const metaRef: { current: SearchMetaEvent | null } = { current: null }
  let pendingSites: SiteResult[] | null = null
  let throttleTimer: ReturnType<typeof setTimeout> | null = null

  const writeCache = (nextSites: SiteResult[], complete = false) => {
    const prev = queryClient.getQueryData<YandexSearchData>(cacheKey)
    queryClient.setQueryData<YandexSearchData>(cacheKey, {
      sites: nextSites,
      meta: metaRef.current,
      complete: complete ? true : prev?.complete,
    })
  }

  const flushSites = () => {
    throttleTimer = null
    if (!pendingSites) return
    writeCache(pendingSites)
    pendingSites = null
  }

  const scheduleSites = (next: SiteResult[]) => {
    pendingSites = next
    if (!throttleTimer) {
      throttleTimer = setTimeout(flushSites, STREAM_UI_THROTTLE_MS)
    }
  }

  const cancelThrottle = () => {
    if (throttleTimer) clearTimeout(throttleTimer)
    throttleTimer = null
    pendingSites = null
  }

  const cached = getYandexSearchCache(queryClient, trimmed, region)
  metaRef.current = cached?.meta ?? null
  if (cached?.sites.length) {
    writeCache(cached.sites)
  }

  const promise = streamYandexSearch(
    { query: trimmed, region: region.trim() || undefined },
    {
      onMeta: (event) => {
        metaRef.current = event
        writeCache(queryClient.getQueryData<YandexSearchData>(cacheKey)?.sites ?? [])
      },
      onData: (event) => scheduleSites(mapStreamSearchResults(event.data)),
      onDone: () => {
        cancelThrottle()
        flushSites()
        const latest = queryClient.getQueryData<YandexSearchData>(cacheKey)
        writeCache(latest?.sites ?? [], true)
        markYandexStreamCompleted(key)
      },
      onError: (err) => {
        cancelThrottle()
        pendingSites = null
        if (err instanceof DOMException && err.name === 'AbortError') return
        const latest = queryClient.getQueryData<YandexSearchData>(cacheKey)
        writeCache(latest?.sites ?? [], true)
        markYandexStreamCompleted(key)
      },
    },
    controller.signal,
  ).catch((err: unknown) => {
    cancelThrottle()
    pendingSites = null
    if (err instanceof DOMException && err.name === 'AbortError') return
    const latest = queryClient.getQueryData<YandexSearchData>(cacheKey)
    writeCache(latest?.sites ?? [], true)
    markYandexStreamCompleted(key)
  })
    .finally(() => {
      const entry = activeYandexStreams.get(key)
      if (entry?.controller === controller) {
        entry.cancelThrottle()
        activeYandexStreams.delete(key)
      }
    })

  activeYandexStreams.set(key, { controller, promise, refs: 1, flush: flushSites, cancelThrottle })

  return {
    promise,
    release: () => {
      const entry = activeYandexStreams.get(key)
      if (!entry) return
      entry.refs -= 1
      if (entry.refs <= 0) {
        entry.cancelThrottle()
        entry.controller.abort()
        activeYandexStreams.delete(key)
      }
    },
  }
}

export function useYandexSearch(query: string, region: string, enabled = true) {
  const queryClient = useQueryClient()
  const trimmed = query.trim()
  const normalizedRegion = normalizeRegion(region)
  const active = enabled && trimmed.length > 0
  const cacheKey = yandexSearchQueryKey(trimmed, normalizedRegion)
  const [streaming, setStreaming] = useState(false)
  const [streamError, setStreamError] = useState<unknown>(null)

  const { data = emptyYandexSearch() } = useQuery({
    queryKey: cacheKey,
    queryFn: () => Promise.reject(new Error('Yandex search stream is managed manually')),
    enabled: false,
    initialData: () => getYandexSearchCache(queryClient, trimmed, region) ?? emptyYandexSearch(),
    staleTime: YANDEX_SEARCH_STALE_MS,
    gcTime: YANDEX_SEARCH_STALE_MS,
  })

  useEffect(() => {
    if (!active) return

    if (isFreshYandexCache(queryClient, trimmed, region)) {
      const cached = getYandexSearchCache(queryClient, trimmed, region)
      if (cached) {
        queryClient.setQueryData(cacheKey, cached)
        return
      }
      completedYandexStreams.delete(streamKeyId(cacheKey))
    }

    const key = streamKeyId(cacheKey)
    const existing = activeYandexStreams.get(key)
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
          existing.cancelThrottle()
          existing.controller.abort()
          activeYandexStreams.delete(key)
        }
      }
    }

    let cancelled = false
    const { promise, release } = acquireYandexSearchStream(queryClient, trimmed, region)

    void Promise.resolve().then(() => {
      if (!cancelled) {
        setStreaming(true)
        setStreamError(null)
      }
    })

    void promise
      .then(() => {
        if (!cancelled) setStreaming(false)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof DOMException && err.name === 'AbortError') return
        setStreamError(err)
        setStreaming(false)
      })

    return () => {
      cancelled = true
      release()
    }
  }, [active, normalizedRegion, queryClient, region, trimmed])

  const loading = active && streaming && !data.complete && data.sites.length === 0

  return {
    sites: active ? data.sites : [],
    meta: active ? data.meta : null,
    loading,
    error: active ? streamError : null,
  }
}

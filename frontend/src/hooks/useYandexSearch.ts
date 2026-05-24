import { streamYandexSearch, type SearchMetaEvent } from '@/api/search'
import { mapStreamSearchResults } from '@/lib/mapStreamSearchResults'
import type { SiteResult } from '@/lib/searchResults'
import { useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

const STREAM_UI_THROTTLE_MS = 250

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

export function getYandexSearchCache(queryClient: QueryClient, query: string, region: string): YandexSearchData | undefined {
  const trimmed = query.trim()
  const exact = queryClient.getQueryData<YandexSearchData>(yandexSearchQueryKey(trimmed, region))
  if (exact?.complete && exact.sites.length > 0) return exact

  const entries = queryClient.getQueriesData<YandexSearchData>({ queryKey: ['yandex-search', trimmed] })
  for (const [, data] of entries) {
    if (data?.complete && data.sites.length > 0) return data
  }

  return exact
}

export function findSiteInYandexSearchCache(queryClient: QueryClient, siteSlug: string, query: string, region: string): SiteResult | undefined {
  const data = getYandexSearchCache(queryClient, query, region)
  return data?.sites.find((site) => site.slug === siteSlug)
}

export function useYandexSearch(query: string, region: string, enabled = true) {
  const queryClient = useQueryClient()
  const trimmed = query.trim()
  const normalizedRegion = normalizeRegion(region)
  const active = enabled && trimmed.length > 0
  const cacheKey = yandexSearchQueryKey(trimmed, normalizedRegion)
  const metaRef = useRef<SearchMetaEvent | null>(null)

  const { data = emptyYandexSearch() } = useQuery({
    queryKey: cacheKey,
    queryFn: emptyYandexSearch,
    enabled: false,
    initialData: () => getYandexSearchCache(queryClient, trimmed, region) ?? emptyYandexSearch(),
    staleTime: Infinity,
    gcTime: 10 * 60 * 1000,
  })

  const [streamError, setStreamError] = useState<unknown>(null)

  useEffect(() => {
    if (!active) return

    const cached = getYandexSearchCache(queryClient, trimmed, region)
    if (cached?.complete) {
      queryClient.setQueryData(cacheKey, cached)
      return
    }

    const controller = new AbortController()
    let pendingSites: SiteResult[] | null = null
    let throttleTimer: ReturnType<typeof setTimeout> | null = null

    const writeCache = (nextSites: SiteResult[], complete = false) => {
      queryClient.setQueryData<YandexSearchData>(cacheKey, {
        sites: nextSites,
        meta: metaRef.current,
        complete: complete || undefined,
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

    metaRef.current = cached?.meta ?? null

    if (!cached?.sites.length) {
      writeCache([])
    }

    void streamYandexSearch(
      { query: trimmed, region: region.trim() || undefined },
      {
        onMeta: (event) => {
          metaRef.current = event
          writeCache(queryClient.getQueryData<YandexSearchData>(cacheKey)?.sites ?? [])
        },
        onData: (event) => scheduleSites(mapStreamSearchResults(event.data)),
        onDone: () => {
          if (throttleTimer) clearTimeout(throttleTimer)
          flushSites()
          const latest = queryClient.getQueryData<YandexSearchData>(cacheKey)
          writeCache(latest?.sites ?? [], true)
        },
        onError: (err) => {
          if (throttleTimer) clearTimeout(throttleTimer)
          pendingSites = null
          if (err instanceof DOMException && err.name === 'AbortError') return
          setStreamError(err)
          writeCache(queryClient.getQueryData<YandexSearchData>(cacheKey)?.sites ?? [], true)
        },
      },
      controller.signal,
    ).catch((err: unknown) => {
      if (throttleTimer) clearTimeout(throttleTimer)
      pendingSites = null
      if (err instanceof DOMException && err.name === 'AbortError') return
      setStreamError(err)
      writeCache(queryClient.getQueryData<YandexSearchData>(cacheKey)?.sites ?? [], true)
    })

    return () => {
      controller.abort()
      if (throttleTimer) clearTimeout(throttleTimer)
    }
  }, [active, cacheKey, queryClient, region, trimmed])

  const loading = active && !data.complete && data.sites.length === 0

  return {
    sites: active ? data.sites : [],
    meta: active ? data.meta : null,
    loading,
    error: active ? streamError : null,
  }
}

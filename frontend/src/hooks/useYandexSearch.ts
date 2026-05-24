import { streamYandexSearch, type SearchMetaEvent } from '@/api/search'
import { mapStreamSearchResults } from '@/lib/mapStreamSearchResults'
import type { SiteResult } from '@/lib/searchResults'
import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

const STREAM_UI_THROTTLE_MS = 250

export type YandexSearchData = {
  sites: SiteResult[]
  meta: SearchMetaEvent | null
}

function normalizeRegion(region: string): string {
  return region.trim().toLowerCase()
}

export function yandexSearchQueryKey(query: string, region: string) {
  return ['yandex-search', query.trim(), normalizeRegion(region)] as const
}

export function findSiteInYandexSearchCache(queryClient: QueryClient, siteSlug: string, query: string, region: string): SiteResult | undefined {
  const data = queryClient.getQueryData<YandexSearchData>(yandexSearchQueryKey(query, region))
  return data?.sites.find((site) => site.slug === siteSlug)
}

export function useYandexSearch(query: string, region: string, enabled = true) {
  const queryClient = useQueryClient()
  const trimmed = query.trim()
  const normalizedRegion = normalizeRegion(region)
  const active = enabled && trimmed.length > 0
  const [sites, setSites] = useState<SiteResult[]>([])
  const [meta, setMeta] = useState<SearchMetaEvent | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const metaRef = useRef<SearchMetaEvent | null>(null)

  useEffect(() => {
    if (!active) return

    const controller = new AbortController()
    const cacheKey = yandexSearchQueryKey(trimmed, normalizedRegion)
    let pendingSites: SiteResult[] | null = null
    let throttleTimer: ReturnType<typeof setTimeout> | null = null

    const writeCache = (nextSites: SiteResult[]) => {
      queryClient.setQueryData<YandexSearchData>(cacheKey, {
        sites: nextSites,
        meta: metaRef.current,
      })
    }

    const flushSites = () => {
      throttleTimer = null
      if (!pendingSites) return
      setSites(pendingSites)
      writeCache(pendingSites)
      pendingSites = null
    }

    const scheduleSites = (next: SiteResult[]) => {
      pendingSites = next
      if (!throttleTimer) {
        throttleTimer = setTimeout(flushSites, STREAM_UI_THROTTLE_MS)
      }
    }

    void Promise.resolve().then(() => {
      if (controller.signal.aborted) return
      metaRef.current = null
      setLoading(true)
      setError(null)
      setSites([])
      setMeta(null)
      writeCache([])
    })

    void streamYandexSearch(
      { query: trimmed, region: normalizedRegion },
      {
        onMeta: (event) => {
          metaRef.current = event
          setMeta(event)
          writeCache(pendingSites ?? [])
        },
        onData: (event) => scheduleSites(mapStreamSearchResults(event.data)),
        onDone: () => {
          if (throttleTimer) clearTimeout(throttleTimer)
          flushSites()
          setLoading(false)
        },
        onError: (err) => {
          if (throttleTimer) clearTimeout(throttleTimer)
          pendingSites = null
          if (err instanceof DOMException && err.name === 'AbortError') return
          setError(err)
          setLoading(false)
        },
      },
      controller.signal,
    ).catch((err: unknown) => {
      if (throttleTimer) clearTimeout(throttleTimer)
      pendingSites = null
      if (err instanceof DOMException && err.name === 'AbortError') return
      setError(err)
      setLoading(false)
    })

    return () => {
      controller.abort()
      if (throttleTimer) clearTimeout(throttleTimer)
    }
  }, [active, trimmed, normalizedRegion, queryClient])

  return {
    sites: active ? sites : [],
    meta: active ? meta : null,
    loading: active && loading,
    error: active ? error : null,
  }
}

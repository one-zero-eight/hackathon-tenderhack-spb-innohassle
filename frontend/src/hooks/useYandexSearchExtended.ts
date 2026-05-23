import { streamYandexSearchExtended, type SearchMetaEvent } from '@/api/search'
import { mapStreamSearchResults } from '@/lib/mapStreamSearchResults'
import type { SiteResult } from '@/lib/searchResults'
import { useEffect, useState } from 'react'

const STREAM_UI_THROTTLE_MS = 250

function normalizeRegion(region: string): string {
  return region.trim().toLowerCase()
}

export function useYandexSearchExtended(query: string, region: string, enabled = true) {
  const trimmed = query.trim()
  const active = enabled && trimmed.length > 0
  const [sites, setSites] = useState<SiteResult[]>([])
  const [meta, setMeta] = useState<SearchMetaEvent | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<unknown>(null)

  useEffect(() => {
    if (!active) return

    const controller = new AbortController()
    let pendingSites: SiteResult[] | null = null
    let throttleTimer: ReturnType<typeof setTimeout> | null = null

    const flushSites = () => {
      throttleTimer = null
      if (pendingSites) {
        setSites(pendingSites)
        pendingSites = null
      }
    }

    const scheduleSites = (next: SiteResult[]) => {
      pendingSites = next
      if (!throttleTimer) {
        throttleTimer = setTimeout(flushSites, STREAM_UI_THROTTLE_MS)
      }
    }

    void Promise.resolve().then(() => {
      if (controller.signal.aborted) return
      setLoading(true)
      setError(null)
      setSites([])
      setMeta(null)
    })

    void streamYandexSearchExtended(
      { query: trimmed, region: normalizeRegion(region) },
      {
        onMeta: setMeta,
        onPage: (event) => scheduleSites(mapStreamSearchResults(event.results)),
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
  }, [active, trimmed, region])

  return {
    sites: active ? sites : [],
    meta: active ? meta : null,
    loading: active && loading,
    error: active ? error : null,
  }
}

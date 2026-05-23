import { streamYandexSearchExtended, type SearchMetaEvent } from '@/api/search'
import { mapStreamSearchResults } from '@/lib/mapStreamSearchResults'
import type { SiteResult } from '@/lib/searchResults'
import { useEffect, useState } from 'react'

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
        onPage: (event) => setSites(mapStreamSearchResults(event.results)),
        onDone: () => setLoading(false),
        onError: (err) => {
          if (err instanceof DOMException && err.name === 'AbortError') return
          setError(err)
          setLoading(false)
        },
      },
      controller.signal,
    ).catch((err: unknown) => {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setError(err)
      setLoading(false)
    })

    return () => controller.abort()
  }, [active, trimmed, region])

  return {
    sites: active ? sites : [],
    meta: active ? meta : null,
    loading: active && loading,
    error: active ? error : null,
  }
}

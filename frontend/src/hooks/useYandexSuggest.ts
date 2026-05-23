import { useEffect, useRef, useState } from 'react'
import {
  fetchYandexSuggest,
  type SuggestItem,
  type SuggestMeta,
} from '../lib/yandexSuggest'

type State = {
  items: SuggestItem[]
  meta?: SuggestMeta
  loading: boolean
  error: string | null
  ready: boolean
  hiddenCount: number
}

const emptyState: State = {
  items: [],
  loading: false,
  error: null,
  ready: false,
  hiddenCount: 0,
}

export function useYandexSuggest(query: string, debounceMs = 250) {
  const [state, setState] = useState<State>(emptyState)
  const requestIdRef = useRef(0)

  useEffect(() => {
    const trimmed = query.trim()
    if (!trimmed) {
      setState(emptyState)
      return
    }

    const requestId = ++requestIdRef.current
    const controller = new AbortController()

    const timer = window.setTimeout(() => {
      setState((prev) => ({ ...prev, loading: true, error: null, ready: false }))

      fetchYandexSuggest(trimmed, controller.signal)
        .then((result) => {
          if (requestId !== requestIdRef.current) return
          setState({
            items: result.items,
            meta: result.meta,
            loading: false,
            error: null,
            ready: true,
            hiddenCount: result.hiddenCount,
          })
        })
        .catch((err: unknown) => {
          if (requestId !== requestIdRef.current) return
          if (err instanceof DOMException && err.name === 'AbortError') {
            setState((prev) =>
              prev.loading ? { ...prev, loading: false } : prev,
            )
            return
          }
          setState({
            items: [],
            loading: false,
            error: err instanceof Error ? err.message : 'Ошибка запроса',
            ready: true,
            hiddenCount: 0,
          })
        })
    }, debounceMs)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
      requestIdRef.current += 1
    }
  }, [query, debounceMs])

  return state
}

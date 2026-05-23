import { fetchYandexSuggest } from '@/lib/yandexSuggest'
import { useEffect, useRef, useState } from 'react'

export function useYandexSuggest(query: string, debounceMs = 250) {
  const trimmed = query.trim()
  const [items, setItems] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const requestIdRef = useRef(0)

  useEffect(() => {
    if (!trimmed) return

    const requestId = ++requestIdRef.current
    const controller = new AbortController()

    const timer = window.setTimeout(() => {
      setLoading(true)

      fetchYandexSuggest(trimmed, controller.signal)
        .then((suggestions) => {
          if (requestId !== requestIdRef.current) return
          setItems(suggestions)
          setLoading(false)
        })
        .catch((err: unknown) => {
          if (requestId !== requestIdRef.current) return
          if (err instanceof DOMException && err.name === 'AbortError') return
          setItems([])
          setLoading(false)
        })
    }, debounceMs)

    return () => {
      window.clearTimeout(timer)
      controller.abort()
      requestIdRef.current += 1
    }
  }, [trimmed, debounceMs])

  if (!trimmed) {
    return { items: [], loading: false }
  }

  return { items, loading }
}

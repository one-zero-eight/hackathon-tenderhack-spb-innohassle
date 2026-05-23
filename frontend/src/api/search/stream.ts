import { isSearchStreamEvent, type SearchStreamEvent } from './events'

export const SEARCH_API_BASE = import.meta.env.VITE_SEARCH_API_URL ?? '/search-api'

export type YandexSearchParams = {
  query: string
  region?: string
}

export type YandexSearchHandlers = {
  onEvent?: (event: SearchStreamEvent) => void
  onMeta?: (event: Extract<SearchStreamEvent, { type: 'meta' }>) => void
  onPage?: (event: Extract<SearchStreamEvent, { type: 'page' }>) => void
  onDone?: () => void
  onError?: (error: unknown) => void
}

function buildSearchUrl(path: '/yandex_search' | '/yandex_search_extended', params: YandexSearchParams): string {
  const url = new URL(`${SEARCH_API_BASE}${path}`, window.location.origin)
  url.searchParams.set('query', params.query.trim())
  if (params.region?.trim()) {
    url.searchParams.set('region', params.region.trim())
  }
  return url.toString()
}

async function readNdjsonStream(response: Response, handlers: YandexSearchHandlers, signal?: AbortSignal): Promise<void> {
  if (!response.ok) {
    throw new Error(`Search HTTP ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('Search stream unavailable')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    if (signal?.aborted) {
      await reader.cancel()
      throw new DOMException('Aborted', 'AbortError')
    }

    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    while (true) {
      const newline = buffer.indexOf('\n')
      if (newline === -1) break

      const line = buffer.slice(0, newline).trim()
      buffer = buffer.slice(newline + 1)
      if (!line) continue

      const parsed: unknown = JSON.parse(line)
      if (!isSearchStreamEvent(parsed)) continue

      handlers.onEvent?.(parsed)

      if (parsed.type === 'meta') handlers.onMeta?.(parsed)
      if (parsed.type === 'page') handlers.onPage?.(parsed)
      if (parsed.type === 'done') {
        handlers.onDone?.()
        return
      }
    }
  }

  handlers.onDone?.()
}

export async function streamYandexSearch(params: YandexSearchParams, handlers: YandexSearchHandlers = {}, signal?: AbortSignal): Promise<void> {
  try {
    const response = await fetch(buildSearchUrl('/yandex_search', params), { signal })
    await readNdjsonStream(response, handlers, signal)
  } catch (error) {
    handlers.onError?.(error)
    throw error
  }
}

export async function streamYandexSearchExtended(params: YandexSearchParams, handlers: YandexSearchHandlers = {}, signal?: AbortSignal): Promise<void> {
  try {
    const response = await fetch(buildSearchUrl('/yandex_search_extended', params), { signal })
    await readNdjsonStream(response, handlers, signal)
  } catch (error) {
    handlers.onError?.(error)
    throw error
  }
}

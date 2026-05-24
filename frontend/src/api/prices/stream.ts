import { isPriceStreamEvent, type PriceStreamEvent } from './events'
import type { PriceSearchStreamState } from './state'
import { applyPriceSearchEvent, emptyPriceSearchResponse } from './state'

export const PRICES_API_BASE = import.meta.env.VITE_API_URL ?? '/api'

export type PriceSearchStreamParams = {
  query: string
  location?: string | null
  limit?: number
  skip?: number
  bypassSpellchecker?: boolean
  /** @default true */
  bypassRelevanceFilter?: boolean
}

export type PriceSearchHandlers = {
  onEvent?: (event: PriceStreamEvent) => void
  onMeta?: (event: Extract<PriceStreamEvent, { type: 'meta' }>) => void
  onBatch?: (event: Extract<PriceStreamEvent, { type: 'batch' }>) => void
  onSourceDone?: (event: Extract<PriceStreamEvent, { type: 'source_done' }>) => void
  onState?: (state: PriceSearchStreamState) => void
  onDone?: (state: PriceSearchStreamState) => void
  onError?: (error: unknown) => void
}

async function readNdjsonStream(response: Response, handlers: PriceSearchHandlers, initialState: PriceSearchStreamState, signal?: AbortSignal): Promise<PriceSearchStreamState> {
  if (!response.ok) {
    throw new Error(`Prices HTTP ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('Price stream unavailable')

  const decoder = new TextDecoder()
  let buffer = ''
  let state = initialState

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
      if (!isPriceStreamEvent(parsed)) continue

      state = applyPriceSearchEvent(state, parsed)
      handlers.onEvent?.(parsed)
      handlers.onState?.(state)

      if (parsed.type === 'meta') handlers.onMeta?.(parsed)
      if (parsed.type === 'batch') handlers.onBatch?.(parsed)
      if (parsed.type === 'source_done') handlers.onSourceDone?.(parsed)
      if (parsed.type === 'done') {
        handlers.onDone?.(state)
        return state
      }
    }
  }

  handlers.onDone?.(state)
  return state
}

export async function streamPriceSearch(params: PriceSearchStreamParams, handlers: PriceSearchHandlers = {}, signal?: AbortSignal): Promise<PriceSearchStreamState> {
  const trimmed = params.query.trim()
  const initialState = emptyPriceSearchResponse(trimmed)

  try {
    const response = await fetch(`${PRICES_API_BASE}/prices/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/x-ndjson',
      },
      body: JSON.stringify({
        query: trimmed,
        limit: params.limit ?? 100,
        skip: params.skip ?? 0,
        location: params.location ?? null,
        bypass_spellchecker: params.bypassSpellchecker ?? false,
        bypass_relevance_filter: params.bypassRelevanceFilter ?? true,
      }),
      signal,
    })

    return await readNdjsonStream(response, handlers, initialState, signal)
  } catch (error) {
    handlers.onError?.(error)
    throw error
  }
}

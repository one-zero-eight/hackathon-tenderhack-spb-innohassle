import { filterPurchaseNoise } from './filterPurchaseNoise'

const SUGGEST_URL = 'https://suggest.yandex.ru/suggest-ya.cgi'
const PROXY_URL = '/yandex-suggest'
const JSONP_TIMEOUT_MS = 8000

type RawSuggestResponse = [string, unknown[]]

function suggestParams(part: string, callback?: string): URLSearchParams {
  const params = new URLSearchParams({ v: '4', fact: '1', part })
  if (callback) params.set('callback', callback)
  return params
}

function parseItemText(raw: unknown): string | null {
  if (typeof raw === 'string') {
    const text = raw.trim()
    return text || null
  }
  if (!Array.isArray(raw) || raw.length < 2) return null
  const text = String(raw[1] ?? '').trim()
  return text || null
}

function parseSuggestBody(text: string): RawSuggestResponse {
  const trimmed = text.trim()
  const jsonp = /^[a-zA-Z_$][\w$]*\s*\(([\s\S]*)\)\s*;?\s*$/u.exec(trimmed)
  const data = JSON.parse(jsonp ? jsonp[1] : trimmed) as unknown
  if (!Array.isArray(data) || data.length < 2) {
    throw new Error('Неожиданный формат ответа suggest')
  }
  return data as RawSuggestResponse
}

function parseResponse(data: RawSuggestResponse): string[] {
  const rawItems = Array.isArray(data[1]) ? data[1] : []
  const texts = rawItems.map(parseItemText).filter((item): item is string => item !== null)
  return filterPurchaseNoise(texts)
}

async function fetchViaProxy(part: string, signal?: AbortSignal): Promise<string[]> {
  const response = await fetch(`${PROXY_URL}?${suggestParams(part)}`, { signal })
  if (!response.ok) throw new Error(`Suggest HTTP ${response.status}`)
  return parseResponse(parseSuggestBody(await response.text()))
}

function fetchViaJsonp(part: string, signal?: AbortSignal): Promise<string[]> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'))
      return
    }

    const callbackName = `jQuery${Date.now()}`
    const script = document.createElement('script')
    script.src = `${SUGGEST_URL}?${suggestParams(part, callbackName)}`
    script.async = true

    let settled = false

    const cleanup = () => {
      delete (window as unknown as Record<string, unknown>)[callbackName]
      script.remove()
      signal?.removeEventListener('abort', onAbort)
      window.clearTimeout(timeoutId)
    }

    const settle = (fn: () => void) => {
      if (settled) return
      settled = true
      cleanup()
      fn()
    }

    const onAbort = () => settle(() => reject(new DOMException('Aborted', 'AbortError')))

    ;(window as unknown as Record<string, (data: RawSuggestResponse) => void>)[callbackName] = (data) => {
      settle(() => resolve(parseResponse(data)))
    }

    script.onerror = () => settle(() => reject(new Error('Не удалось загрузить подсказки')))
    script.onload = () => {
      window.setTimeout(() => {
        if (!settled) settle(() => reject(new Error('Таймаут JSONP')))
      }, 50)
    }

    const timeoutId = window.setTimeout(() => {
      if (!settled) settle(() => reject(new Error('Таймаут подсказок')))
    }, JSONP_TIMEOUT_MS)

    signal?.addEventListener('abort', onAbort)
    document.head.appendChild(script)
  })
}

export async function fetchYandexSuggest(part: string, signal?: AbortSignal): Promise<string[]> {
  const trimmed = part.trim()
  if (!trimmed) return []

  try {
    return await fetchViaProxy(trimmed, signal)
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
  }

  return fetchViaJsonp(trimmed, signal)
}

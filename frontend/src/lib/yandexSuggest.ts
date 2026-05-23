import { filterPurchaseNoise } from './filterPurchaseNoise'

const SUGGEST_URL = 'https://suggest.yandex.ru/suggest-ya.cgi'
/** Прокси Vite: обход CORS в dev/preview */
const PROXY_URL = '/yandex-suggest'

function suggestParams(part: string, withCallback?: string): URLSearchParams {
  const params = new URLSearchParams({
    v: '4',
    fact: '1',
    part,
  })
  if (withCallback) {
    params.set('callback', withCallback)
  }
  return params
}

export type SuggestItem = {
  text: string
  type: 'plain' | 'fact' | 'nav'
  extra?: string
  url?: string
}

export type SuggestMeta = {
  r?: number
  log?: string
  continue?: string
}

export type SuggestResult = {
  query: string
  items: SuggestItem[]
  meta?: SuggestMeta
  /** Сколько подсказок скрыто фильтром площадок/цены/локации */
  hiddenCount: number
}

type RawSuggestResponse = [string, unknown[], SuggestMeta?]

declare global {
  interface Window {
    [key: string]: unknown
  }
}

function parseItem(raw: unknown): SuggestItem | null {
  if (typeof raw === 'string') {
    return { text: raw, type: 'plain' }
  }

  if (!Array.isArray(raw) || raw.length < 2) {
    return null
  }

  const kind = raw[0]
  const text = String(raw[1] ?? '')

  if (kind === 'fact') {
    return { text, type: 'fact', extra: raw[2] != null ? String(raw[2]) : undefined }
  }

  if (kind === 'nav') {
    return {
      text,
      type: 'nav',
      extra: raw[2] != null ? String(raw[2]) : undefined,
      url: raw[3] != null ? String(raw[3]) : undefined,
    }
  }

  if (kind === '' || kind == null) {
    return { text, type: 'plain', extra: raw[2] != null ? String(raw[2]) : undefined }
  }

  return { text, type: 'plain' }
}

function normalizeRawItems(raw: unknown): unknown[] {
  if (Array.isArray(raw)) return raw
  return []
}

function parseSuggestBody(text: string): RawSuggestResponse {
  const trimmed = text.trim()
  const jsonp = /^[a-zA-Z_$][\w$]*\s*\(([\s\S]*)\)\s*;?\s*$/u.exec(trimmed)
  const json = jsonp ? jsonp[1] : trimmed
  const data = JSON.parse(json) as unknown
  if (!Array.isArray(data) || data.length < 2) {
    throw new Error('Неожиданный формат ответа suggest')
  }
  return data as RawSuggestResponse
}

function parseResponse(data: RawSuggestResponse): SuggestResult {
  const [query, rawItems, meta] = data
  const parsed = normalizeRawItems(rawItems)
    .map(parseItem)
    .filter((item): item is SuggestItem => item !== null)
  const { items, hiddenCount } = filterPurchaseNoise(parsed)

  return { query: String(query ?? ''), items, meta, hiddenCount }
}

async function fetchViaProxy(
  part: string,
  signal?: AbortSignal,
): Promise<SuggestResult> {
  const url = `${PROXY_URL}?${suggestParams(part)}`
  const response = await fetch(url, { signal })
  if (!response.ok) {
    throw new Error(`Suggest HTTP ${response.status}`)
  }
  const data = parseSuggestBody(await response.text())
  return parseResponse(data)
}

/**
 * GET к suggest.yandex.ru через JSONP.
 * Имя callback должно быть из «белого списка» (например jQuery123), иначе
 * сервер отдаёт голый JSON → Firefox: NS_ERROR_CORRUPTED_CONTENT.
 */
const JSONP_TIMEOUT_MS = 8000

function fetchViaJsonp(part: string, signal?: AbortSignal): Promise<SuggestResult> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'))
      return
    }

    // Яндекс оборачивает ответ только для имён вроде jQuery123
    const callbackName = `jQuery${Date.now()}`
    const params = suggestParams(part, callbackName)

    const script = document.createElement('script')
    script.src = `${SUGGEST_URL}?${params}`
    script.async = true

    let settled = false

    const cleanup = () => {
      delete window[callbackName]
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

    const onAbort = () => {
      settle(() => reject(new DOMException('Aborted', 'AbortError')))
    }

    window[callbackName] = (data: RawSuggestResponse) => {
      settle(() => resolve(parseResponse(data)))
    }

    script.onerror = () => {
      settle(() => reject(new Error('Не удалось загрузить подсказки (JSONP)')))
    }

    // Голый JSON в <script> выполняется без вызова callback — зависание
    script.onload = () => {
      window.setTimeout(() => {
        if (!settled) {
          settle(() =>
            reject(
              new Error(
                'Suggest вернул JSON без JSONP. Запустите через pnpm dev (нужен прокси /yandex-suggest).',
              ),
            ),
          )
        }
      }, 50)
    }

    const timeoutId = window.setTimeout(() => {
      if (!settled) {
        settle(() => reject(new Error('Таймаут загрузки подсказок')))
      }
    }, JSONP_TIMEOUT_MS)

    signal?.addEventListener('abort', onAbort)
    document.head.appendChild(script)
  })
}

export async function fetchYandexSuggest(
  part: string,
  signal?: AbortSignal,
): Promise<SuggestResult> {
  const trimmed = part.trim()
  if (!trimmed) {
    return { query: '', items: [], hiddenCount: 0 }
  }

  if (!signal?.aborted) {
    try {
      return await fetchViaProxy(trimmed, signal)
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        throw err
      }
      // нет прокси (статический хостинг) — JSONP ниже
    }
  }

  return fetchViaJsonp(trimmed, signal)
}

export function buildSuggestUrl(part: string): string {
  const trimmed = part.trim()
  if (!trimmed) {
    return `${SUGGEST_URL}?v=4&fact=1`
  }
  return `${SUGGEST_URL}?${suggestParams(trimmed)}`
}

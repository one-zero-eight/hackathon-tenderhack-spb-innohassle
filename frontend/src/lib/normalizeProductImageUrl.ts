const YANDEX_AVATARS_ORIGIN = 'https://avatars.mds.yandex.net'
const BROKEN_YANDEX_MARKET_AVATAR = /^https?:\/\/market\.yandex\.ru(\/get-[^?#]+)/i

export function normalizeProductImageUrl(url: string | null | undefined): string | null {
  if (url == null) return null

  const trimmed = url.trim()
  if (!trimmed) return null

  if (trimmed.startsWith('//')) {
    return `https:${trimmed}`
  }

  if (trimmed.startsWith('/get-')) {
    return `${YANDEX_AVATARS_ORIGIN}${trimmed}`
  }

  const brokenMarketAvatar = trimmed.match(BROKEN_YANDEX_MARKET_AVATAR)
  if (brokenMarketAvatar) {
    return `${YANDEX_AVATARS_ORIGIN}${brokenMarketAvatar[1]}`
  }

  return trimmed
}

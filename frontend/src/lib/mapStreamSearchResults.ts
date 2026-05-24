import type { SearchShop } from '@/api/search/events'
import { normalizeProductImageUrl } from '@/lib/normalizeProductImageUrl'
import type { Product, SiteResult } from '@/lib/searchResults'

function slugifyHostname(hostname: string): string {
  return hostname
    .toLowerCase()
    .replace(/^www\./, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

function parsePriceText(value: string | null | undefined): number | null {
  if (!value) return null
  const digits = value.replace(/[^\d]/g, '')
  if (!digits) return null
  const parsed = Number.parseInt(digits, 10)
  return Number.isFinite(parsed) ? parsed : null
}

function productId(slug: string, href: string | null | undefined, index: number): string {
  if (href) {
    let hash = 0
    for (let i = 0; i < href.length; i++) hash = (hash * 31 + href.charCodeAt(i)) | 0
    return `${slug}-${Math.abs(hash).toString(36)}`
  }
  return `${slug}-${index}`
}

function parseRatingText(value: string | null | undefined): number | null {
  if (!value) return null
  const parsed = Number.parseFloat(value.replace(',', '.').trim())
  return Number.isFinite(parsed) ? parsed : null
}

function mapStreamProduct(shop: SearchShop, product: SearchShop['products'][number], index: number): Product | null {
  const slug = slugifyHostname(shop.hostname)
  const href = product.href ?? undefined
  const trimmedName = product.title?.trim()
  if (!trimmedName) return null

  return {
    id: productId(slug, href, index),
    name: trimmedName,
    price: parsePriceText(product.price) ?? 0,
    url: href ?? null,
    imageUrl: normalizeProductImageUrl(product.thumbnail),
  }
}

export function mapStreamSearchResults(shops: SearchShop[]): SiteResult[] {
  return shops
    .map((shop) => {
      const slug = slugifyHostname(shop.hostname)
      const products = shop.products.map((product, index) => mapStreamProduct(shop, product, index)).filter((product): product is Product => product !== null)
      const rating = parseRatingText(shop.rating)
      const reviewsLabel = shop.reviews?.trim()

      return {
        slug,
        name: shop.hostname,
        kind: 'other' as const,
        products,
        logo: shop.favicon ? normalizeProductImageUrl(shop.favicon) ?? shop.favicon : undefined,
        rating: rating ?? undefined,
        reviewsLabel: reviewsLabel || undefined,
      }
    })
    .filter((site) => site.products.length > 0)
}

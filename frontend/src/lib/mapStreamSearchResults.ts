import type { SearchHostnameGroup, SearchStreamProduct } from '@/api/search/events'
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

function mapStreamProduct(product: SearchStreamProduct, slug: string, index: number): Product | null {
  const href = product.href ?? undefined
  const name = product.extracted ? (product.name ?? product.title) : product.title
  const priceText = product.extracted ? (product.cost ?? product.price) : product.price
  const price = parsePriceText(priceText)
  const trimmedName = name?.trim()

  if (!trimmedName) return null

  return {
    id: productId(slug, href, index),
    name: trimmedName,
    price: price ?? 0,
    url: href ?? null,
    imageUrl: normalizeProductImageUrl(product.thumbnail),
  }
}

export function mapStreamSearchResults(groups: SearchHostnameGroup[]): SiteResult[] {
  return groups
    .map((group) => {
      const slug = slugifyHostname(group.hostname)
      const products = group.products
        .map((product, index) => mapStreamProduct(product, slug, index))
        .filter((product): product is Product => product !== null)

      return {
        slug,
        name: group.hostname,
        kind: 'other' as const,
        products,
      }
    })
    .filter((site) => site.products.length > 0)
}

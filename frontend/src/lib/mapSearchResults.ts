import type { SchemaPriceSearchResponse, SchemaProductPrice } from '@/api/types.ts'
import { MARKETPLACE_LOGOS, type Product, type SiteKind, type SiteResult } from '@/lib/searchResults'

type SourceMeta = {
  slug: string
  name: string
  kind: SiteKind
  logo?: string
}

const SOURCE_META: Record<string, SourceMeta> = {
  Wildberries: {
    slug: 'wildberries',
    name: 'Wildberries',
    kind: 'wildberries',
    logo: MARKETPLACE_LOGOS.wildberries,
  },
  'Yandex Market': {
    slug: 'yandex-market',
    name: 'Yandex.Market',
    kind: 'yandex',
    logo: MARKETPLACE_LOGOS.yandexMarket,
  },
}

function slugifySource(source: string): string {
  return source
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

function productId(slug: string, url: string | null | undefined, index: number): string {
  if (url) {
    let hash = 0
    for (let i = 0; i < url.length; i++) hash = (hash * 31 + url.charCodeAt(i)) | 0
    return `${slug}-${Math.abs(hash).toString(36)}`
  }
  return `${slug}-${index}`
}

function mapProduct(item: SchemaProductPrice, slug: string, index: number): Product {
  return {
    id: productId(slug, item.url, index),
    name: item.name?.trim() || 'Без названия',
    price: Math.round(item.price),
    brand: item.brand,
    originalPrice: item.original_price != null ? Math.round(item.original_price) : null,
    url: item.url,
    imageUrl: item.image_url,
  }
}

function mapMarketplaceResult(result: SchemaPriceSearchResponse['results'][number]): SiteResult | null {
  const meta = SOURCE_META[result.source] ?? {
    slug: slugifySource(result.source),
    name: result.source,
    kind: 'other' as const,
  }

  return {
    slug: meta.slug,
    name: meta.name,
    kind: meta.kind,
    logo: meta.logo,
    products: result.prices.map((price, index) => mapProduct(price, meta.slug, index)),
    error: result.error,
  }
}

export function mapPriceSearchResponse(response: SchemaPriceSearchResponse): SiteResult[] {
  return response.results.map(mapMarketplaceResult).filter((site): site is SiteResult => site !== null)
}

export function splitSiteResults(sites: SiteResult[]) {
  return {
    main: sites.filter((site) => site.kind !== 'other'),
    other: sites.filter((site) => site.kind === 'other'),
  }
}

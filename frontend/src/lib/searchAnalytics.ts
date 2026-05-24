import type { Product, SiteKind, SiteResult } from '@/lib/searchResults'

export const KIND_LABELS: Record<SiteKind, string> = {
  ozon: 'OZON',
  wildberries: 'Wildberries',
  yandex: 'Yandex Market',
  other: 'Другие источники',
}

export const KIND_COLORS: Record<SiteKind, string> = {
  ozon: '#2563eb',
  wildberries: '#c026d3',
  yandex: '#ea580c',
  other: '#264b82',
}

export type AnalyticsSegment = {
  id: string
  label: string
  value: number
  color: string
}

export type AnalyticsSiteRow = {
  slug: string
  name: string
  kind: SiteKind
  productCount: number
  pricedCount: number
  avgPrice: number | null
  medianPrice: number | null
  minPrice: number | null
  maxPrice: number | null
  rating: number | null
}

export type AnalyticsProductRow = {
  id: string
  name: string
  price: number
  siteName: string
  siteSlug: string
  kind: SiteKind
  imageUrl?: string | null
  url?: string | null
}

export type SearchAnalytics = {
  query: string
  summary: {
    siteCount: number
    productCount: number
    pricedCount: number
    marketplaceSites: number
    otherSites: number
    minPrice: number | null
    maxPrice: number | null
    avgPrice: number | null
    medianPrice: number | null
    spread: number | null
    discountCount: number
    avgDiscountPct: number | null
  }
  byKind: AnalyticsSegment[]
  bySite: AnalyticsSiteRow[]
  priceHistogram: AnalyticsSegment[]
  topCheapest: AnalyticsProductRow[]
  topExpensive: AnalyticsProductRow[]
  ratedSites: { name: string; rating: number; productCount: number }[]
}

function median(values: number[]): number | null {
  if (values.length === 0) return null
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  if (sorted.length % 2 === 0) return Math.round((sorted[mid - 1] + sorted[mid]) / 2)
  return sorted[mid]
}

function allPricedRows(sites: SiteResult[]): { product: Product; site: SiteResult }[] {
  const rows: { product: Product; site: SiteResult }[] = []
  for (const site of sites) {
    for (const product of site.products) {
      if (product.price > 0) rows.push({ product, site })
    }
  }
  return rows
}

function buildHistogram(prices: number[]): AnalyticsSegment[] {
  if (prices.length === 0) return []

  const min = Math.min(...prices)
  const max = Math.max(...prices)
  const bucketCount = Math.min(8, Math.max(4, Math.ceil(prices.length / 12)))
  const span = Math.max(max - min, 1)
  const step = Math.ceil(span / bucketCount / 100) * 100 || 100

  const buckets = new Map<string, number>()
  for (const price of prices) {
    const index = Math.min(Math.floor((price - min) / step), bucketCount - 1)
    const low = min + index * step
    const high = low + step
    const label = `${formatBucket(low)}–${formatBucket(high)}`
    buckets.set(label, (buckets.get(label) ?? 0) + 1)
  }

  const shades = ['#c5d4e8', '#9bb4d4', '#7394c0', '#4f74ac', '#264b82', '#1e3d68', '#162f4f', '#0f2136']
  return [...buckets.entries()].map(([label, value], i) => ({
    id: `bucket-${i}`,
    label,
    value,
    color: shades[i % shades.length],
  }))
}

function formatBucket(n: number): string {
  if (n >= 1000) return `${Math.round(n / 1000)}k`
  return String(Math.round(n))
}

export function buildSearchAnalytics(sites: SiteResult[], query: string): SearchAnalytics {
  const pricedRows = allPricedRows(sites)
  const prices = pricedRows.map((r) => r.product.price)
  const minPrice = prices.length > 0 ? Math.min(...prices) : null
  const maxPrice = prices.length > 0 ? Math.max(...prices) : null
  const avgPrice = prices.length > 0 ? Math.round(prices.reduce((s, p) => s + p, 0) / prices.length) : null
  const medianPrice = median(prices)

  const discountRows = pricedRows.filter((r) => r.product.originalPrice != null && r.product.originalPrice > r.product.price)
  const discountPcts = discountRows.map((r) => Math.round((1 - r.product.price / r.product.originalPrice!) * 100))

  const kindCounts: Record<SiteKind, number> = { ozon: 0, wildberries: 0, yandex: 0, other: 0 }
  for (const site of sites) {
    kindCounts[site.kind] += site.products.filter((p) => p.price > 0).length
  }

  const byKind: AnalyticsSegment[] = (Object.keys(kindCounts) as SiteKind[])
    .filter((kind) => kindCounts[kind] > 0)
    .map((kind) => ({
      id: kind,
      label: KIND_LABELS[kind],
      value: kindCounts[kind],
      color: KIND_COLORS[kind],
    }))

  const bySite: AnalyticsSiteRow[] = sites
    .map((site) => {
      const sitePrices = site.products.map((p) => p.price).filter((p) => p > 0)
      return {
        slug: site.slug,
        name: site.name,
        kind: site.kind,
        productCount: site.products.length,
        pricedCount: sitePrices.length,
        avgPrice: sitePrices.length > 0 ? Math.round(sitePrices.reduce((s, p) => s + p, 0) / sitePrices.length) : null,
        medianPrice: median(sitePrices),
        minPrice: sitePrices.length > 0 ? Math.min(...sitePrices) : null,
        maxPrice: sitePrices.length > 0 ? Math.max(...sitePrices) : null,
        rating: site.rating ?? null,
      }
    })
    .filter((row) => row.pricedCount > 0)
    .sort((a, b) => (a.minPrice ?? Infinity) - (b.minPrice ?? Infinity))

  const toProductRow = (r: { product: Product; site: SiteResult }): AnalyticsProductRow => ({
    id: r.product.id,
    name: r.product.name,
    price: r.product.price,
    siteName: r.site.name,
    siteSlug: r.site.slug,
    kind: r.site.kind,
    imageUrl: r.product.imageUrl,
    url: r.product.url,
  })

  const sortedByPrice = [...pricedRows].sort((a, b) => a.product.price - b.product.price)

  return {
    query,
    summary: {
      siteCount: sites.filter((s) => s.products.some((p) => p.price > 0)).length,
      productCount: sites.reduce((n, s) => n + s.products.length, 0),
      pricedCount: prices.length,
      marketplaceSites: sites.filter((s) => s.kind !== 'other' && s.products.some((p) => p.price > 0)).length,
      otherSites: sites.filter((s) => s.kind === 'other' && s.products.some((p) => p.price > 0)).length,
      minPrice,
      maxPrice,
      avgPrice,
      medianPrice,
      spread: minPrice != null && maxPrice != null ? maxPrice - minPrice : null,
      discountCount: discountRows.length,
      avgDiscountPct: discountPcts.length > 0 ? Math.round(discountPcts.reduce((s, p) => s + p, 0) / discountPcts.length) : null,
    },
    byKind,
    bySite,
    priceHistogram: buildHistogram(prices),
    topCheapest: sortedByPrice.slice(0, 8).map(toProductRow),
    topExpensive: sortedByPrice.slice(-8).reverse().map(toProductRow),
    ratedSites: sites
      .filter((s) => s.rating != null)
      .map((s) => ({ name: s.name, rating: s.rating!, productCount: s.products.length }))
      .sort((a, b) => b.rating - a.rating),
  }
}

export function hasAnalyticsData(sites: SiteResult[]): boolean {
  return sites.some((site) => site.products.some((product) => product.price > 0))
}

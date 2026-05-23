import { eventsFetch } from '@/api/core'
import type { SchemaPriceSearchRequest, SchemaPriceSearchResponse } from '@/api/core/types'
import { mapPriceSearchResponse } from '@/lib/mapSearchResults'
import type { SiteResult } from '@/lib/searchResults'
import { useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'

export const PRICE_SEARCH_LIMIT = 100
export const PRICE_SEARCH_STALE_MS = 5 * 60 * 1000

export type PriceSearchParams = {
  query: string
  location?: string | null
  limit?: number
  skip?: number
  bypassSpellchecker?: boolean
}

export type PriceSearchData = {
  sites: SiteResult[]
  fixedQuery: string | null
  effectiveQuery: string
}

export function priceSearchQueryKey({ query, location, limit = PRICE_SEARCH_LIMIT, skip = 0, bypassSpellchecker = false }: PriceSearchParams) {
  return ['price-search', query.trim(), location ?? '', limit, skip, bypassSpellchecker] as const
}

function mapPriceSearchData(data: SchemaPriceSearchResponse): PriceSearchData {
  const fixedQuery = data.fixed_query?.trim() || null
  return {
    sites: mapPriceSearchResponse(data),
    fixedQuery,
    effectiveQuery: fixedQuery ?? data.query,
  }
}

export function findSiteInPriceSearchCache(queryClient: QueryClient, siteSlug: string, location?: string | null): SiteResult | undefined {
  const normalizedLocation = location ?? ''
  const entries = queryClient.getQueriesData<SchemaPriceSearchResponse>({ queryKey: ['price-search'] })

  for (const [queryKey, data] of entries) {
    if (!data) continue
    if (queryKey[2] !== normalizedLocation) continue
    const site = mapPriceSearchData(data).sites.find((item) => item.slug === siteSlug)
    if (site) return site
  }

  return undefined
}

export function findProductInPriceSearchCache(queryClient: QueryClient, siteSlug: string, productId: string, location?: string | null) {
  const site = findSiteInPriceSearchCache(queryClient, siteSlug, location)
  if (!site) return null
  const product = site.products.find((item) => item.id === productId)
  if (!product) return null
  return { site, product }
}

export async function fetchPriceSearch(params: PriceSearchParams): Promise<SchemaPriceSearchResponse> {
  const body: SchemaPriceSearchRequest = {
    query: params.query.trim(),
    limit: params.limit ?? PRICE_SEARCH_LIMIT,
    skip: params.skip ?? 0,
    location: params.location ?? null,
    bypass_spellchecker: params.bypassSpellchecker ?? false,
  }

  const { data, error } = await eventsFetch.POST('/prices/search', { body })
  if (error || !data) throw error ?? new Error('Search failed')
  return data
}

export function usePriceSearch(params: PriceSearchParams, enabled = true) {
  const trimmed = params.query.trim()

  return useQuery({
    queryKey: priceSearchQueryKey(params),
    queryFn: () => fetchPriceSearch(params),
    enabled: enabled && trimmed.length > 0,
    staleTime: PRICE_SEARCH_STALE_MS,
    select: mapPriceSearchData,
  })
}

export function useSiteFromSearch(siteSlug: string, params: PriceSearchParams): SiteResult | undefined {
  const queryClient = useQueryClient()
  const trimmed = params.query.trim()
  if (!trimmed) return findSiteInPriceSearchCache(queryClient, siteSlug, params.location)

  const data = queryClient.getQueryData<SchemaPriceSearchResponse>(priceSearchQueryKey(params))
  if (data) {
    return mapPriceSearchData(data).sites.find((site) => site.slug === siteSlug)
  }

  return findSiteInPriceSearchCache(queryClient, siteSlug, params.location)
}

export function useProductFromSearch(siteSlug: string, productId: string, params: PriceSearchParams) {
  const queryClient = useQueryClient()
  const site = useSiteFromSearch(siteSlug, params)
  const cached = findProductInPriceSearchCache(queryClient, siteSlug, params.location)
  const resolvedSite = site ?? cached
  if (!resolvedSite) return null
  const product = resolvedSite.products.find((item) => item.id === productId)
  if (!product) return null
  return { site: resolvedSite, product }
}

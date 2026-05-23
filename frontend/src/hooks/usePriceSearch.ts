import { eventsFetch } from '@/api'
import type { SchemaPriceSearchRequest, SchemaPriceSearchResponse } from '@/api/types.ts'
import { mapPriceSearchResponse } from '@/lib/mapSearchResults'
import type { SiteResult } from '@/lib/searchResults'
import { useQuery, useQueryClient } from '@tanstack/react-query'

export const PRICE_SEARCH_LIMIT = 100

export type PriceSearchParams = {
  query: string
  location?: string | null
  limit?: number
  skip?: number
}

export function priceSearchQueryKey({ query, location, limit = PRICE_SEARCH_LIMIT, skip = 0 }: PriceSearchParams) {
  return ['price-search', query.trim(), location ?? '', limit, skip] as const
}

export async function fetchPriceSearch(params: PriceSearchParams): Promise<SchemaPriceSearchResponse> {
  const body: SchemaPriceSearchRequest = {
    query: params.query.trim(),
    limit: params.limit ?? PRICE_SEARCH_LIMIT,
    skip: params.skip ?? 0,
    location: params.location ?? null,
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
    select: (data) => mapPriceSearchResponse(data),
  })
}

export function useSiteFromSearch(siteSlug: string, params: PriceSearchParams): SiteResult | undefined {
  const queryClient = useQueryClient()
  const trimmed = params.query.trim()
  if (!trimmed) return undefined

  const data = queryClient.getQueryData<SchemaPriceSearchResponse>(priceSearchQueryKey(params))
  if (!data) return undefined
  return mapPriceSearchResponse(data).find((site) => site.slug === siteSlug)
}

export function useProductFromSearch(siteSlug: string, productId: string, params: PriceSearchParams) {
  const site = useSiteFromSearch(siteSlug, params)
  if (!site) return null
  const product = site.products.find((item) => item.id === productId)
  if (!product) return null
  return { site, product }
}

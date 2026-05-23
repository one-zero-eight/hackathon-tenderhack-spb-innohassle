import type { PriceSearchStreamState } from '@/api/prices'
import { mapMarketplaceResult, type PriceSearchData } from '@/lib/mapSearchResults'
import type { SiteResult } from '@/lib/searchResults'

export function createPriceSearchMapper() {
  const sitesBySlug = new Map<string, SiteResult>()
  const priceCounts = new Map<string, number>()

  return {
    update(state: PriceSearchStreamState): PriceSearchData {
      for (const result of state.results) {
        const count = result.prices.length
        const prevCount = priceCounts.get(result.source) ?? -1
        const needsRemap = count !== prevCount || result.complete
        if (!needsRemap) continue

        priceCounts.set(result.source, count)
        const site = mapMarketplaceResult(result)
        if (site) sitesBySlug.set(site.slug, site)
      }

      const fixedQuery = state.fixed_query?.trim() || null
      return {
        sites: [...sitesBySlug.values()],
        fixedQuery,
        effectiveQuery: fixedQuery ?? state.query,
      }
    },
    reset() {
      sitesBySlug.clear()
      priceCounts.clear()
    },
  }
}

export function emptyPriceSearchData(query: string): PriceSearchData {
  return { sites: [], fixedQuery: null, effectiveQuery: query }
}

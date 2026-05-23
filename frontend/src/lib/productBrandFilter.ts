import type { Product } from '@/lib/searchResults'

/** Sentinel id for products without a brand in filter UI. */
export const NO_BRAND_FILTER_ID = '__no_brand__'

export const NO_BRAND_FILTER_LABEL = 'Бренд не указан'

export type BrandFilterOption = {
  id: string
  label: string
  count: number
}

export function getProductBrandFilterId(product: Product): string {
  const brand = product.brand?.trim()
  return brand ? brand : NO_BRAND_FILTER_ID
}

export function getBrandFilterOptions(products: Product[]): BrandFilterOption[] {
  const counts = new Map<string, number>()

  for (const product of products) {
    const id = getProductBrandFilterId(product)
    counts.set(id, (counts.get(id) ?? 0) + 1)
  }

  const options: BrandFilterOption[] = []

  for (const [id, count] of counts) {
    if (id === NO_BRAND_FILTER_ID) continue
    options.push({ id, label: id, count })
  }

  options.sort((a, b) => a.label.localeCompare(b.label, 'ru'))

  const noBrandCount = counts.get(NO_BRAND_FILTER_ID)
  if (noBrandCount) {
    options.unshift({ id: NO_BRAND_FILTER_ID, label: NO_BRAND_FILTER_LABEL, count: noBrandCount })
  }

  return options
}

export function filterProductsByBrands(products: Product[], selectedBrandIds: ReadonlySet<string>): Product[] {
  if (selectedBrandIds.size === 0) return products
  return products.filter((product) => selectedBrandIds.has(getProductBrandFilterId(product)))
}

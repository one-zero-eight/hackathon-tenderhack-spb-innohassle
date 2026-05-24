import { Link, Outlet, createFileRoute, redirect, useRouterState } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'
import { IoArrowBack, IoGridOutline, IoListOutline, IoSearch, IoDownloadOutline } from 'react-icons/io5'
import SiteTitle from '@/components/shared/SiteTitle'
import { findSiteInYandexSearchCache } from '@/hooks/useYandexSearch'
import { useQueryClient } from '@tanstack/react-query'
import { ProductCard } from '@/components/shared/ProductCard'
import PriceRangeSlider from '@/components/shared/PriceRangeSlider'
import { ResultsSkeleton } from '@/components/shared/ResultsSkeleton'
import SortDropdown from '@/components/shared/SortDropdown'
import Input from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useCity } from '@/hooks/useCity'
import { usePriceSearch } from '@/hooks/usePriceSearch'
import { cn } from '@/lib/cn'
import { getCityLocation, getPopularCities, NO_CITY_OPTION } from '@/lib/geo'
import { exportSiteProductsToCsv } from '@/lib/exportCsv'
import { filterProductsByBrands, getBrandFilterOptions } from '@/lib/productBrandFilter'
import { filterProductsByLocalSearch } from '@/lib/productLocalSearch'
import { formatPrice, type Product, type SiteKind, type SiteResult } from '@/lib/searchResults'

type CategorySearch = {
  q?: string
  location?: string
}

type SortValue = 'relevant' | 'price-asc' | 'price-desc' | 'name-asc' | 'name-desc'
type ViewMode = 'grid' | 'rows'

export const Route = createFileRoute('/sites/$siteName')({
  validateSearch: (search: Record<string, unknown>): CategorySearch => ({
    q: typeof search.q === 'string' ? search.q : '',
    location: typeof search.location === 'string' ? search.location : undefined,
  }),
  beforeLoad: ({ params, search }) => {
    if (params.siteName === 'analytics') {
      const parsed = search as Record<string, unknown>
      throw redirect({
        to: '/sites/analytics',
        search: {
          q: typeof parsed.q === 'string' ? parsed.q : '',
          location: typeof parsed.location === 'string' ? parsed.location : undefined,
          strict: parsed.strict === true || parsed.strict === 'true' || parsed.strict === '1' ? true : undefined,
        },
      })
    }
  },
  component: CategoryPage,
})

const sortOptions = [
  { value: 'relevant', label: 'По популярности' },
  { value: 'price-asc', label: 'По возрастанию цены' },
  { value: 'price-desc', label: 'По убыванию цены' },
  { value: 'name-asc', label: 'По названию (А-Я)' },
  { value: 'name-desc', label: 'По названию (Я-А)' },
]

const siteAccent: Record<
  SiteKind,
  {
    link: string
    badge: string
    chip: string
    viewActive: string
    sortRadioRing: string
    sortRadioDot: string
    sliderTrack: string
    sliderFill: string
    sliderThumb: string
    resetButton: string
    exportButton: string
  }
> = {
  ozon: {
    link: 'text-blue-600 hover:text-blue-700',
    badge: 'bg-blue-600 text-white',
    chip: 'border-blue-100 bg-blue-50 text-blue-800',
    viewActive: 'text-blue-600',
    sortRadioRing: 'border-blue-600',
    sortRadioDot: 'bg-blue-600',
    sliderTrack: 'bg-blue-100',
    sliderFill: 'bg-blue-600',
    sliderThumb: '[&::-moz-range-thumb]:border-blue-600 [&::-webkit-slider-thumb]:border-blue-600',
    resetButton: 'bg-blue-500 text-white hover:bg-blue-600',
    exportButton: 'border bg-blue-200/30 border-blue-600 text-blue-600 hover:bg-blue-600/10',
  },
  wildberries: {
    link: 'text-fuchsia-600 hover:text-fuchsia-700',
    badge: 'bg-fuchsia-600 text-white',
    chip: 'border-fuchsia-100 bg-fuchsia-50 text-fuchsia-800',
    viewActive: 'text-fuchsia-600',
    sortRadioRing: 'border-fuchsia-600',
    sortRadioDot: 'bg-fuchsia-600',
    sliderTrack: 'bg-fuchsia-100',
    sliderFill: 'bg-fuchsia-600',
    sliderThumb: '[&::-moz-range-thumb]:border-fuchsia-600 [&::-webkit-slider-thumb]:border-fuchsia-600',
    resetButton: 'bg-fuchsia-500 text-white hover:bg-fuchsia-600',
    exportButton: 'border border-fuchsia-600 bg-fuchsia-200/30 text-fuchsia-600 hover:bg-fuchsia-600/10',
  },
  yandex: {
    link: 'text-yellow-700 hover:text-yellow-800',
    badge: 'bg-yellow-500 text-white',
    chip: 'border-yellow-100 bg-yellow-50 text-yellow-900',
    viewActive: 'text-yellow-500',
    sortRadioRing: 'border-yellow-500',
    sortRadioDot: 'bg-yellow-500',
    sliderTrack: 'bg-yellow-100',
    sliderFill: 'bg-yellow-500',
    sliderThumb: '[&::-moz-range-thumb]:border-yellow-500 [&::-webkit-slider-thumb]:border-yellow-500',
    resetButton: 'bg-yellow-500 text-white hover:bg-yellow-600',
    exportButton: 'border border-yellow-600 text-yellow-600 bg-yellow-200/30 hover:bg-yellow-600/10',
  },
  other: {
    link: 'text-main-blue hover:underline',
    badge: 'bg-main-blue text-white',
    chip: 'border-gray-blue bg-pale-blue text-black',
    viewActive: 'text-main-blue',
    sortRadioRing: 'border-main-blue',
    sortRadioDot: 'bg-main-blue',
    sliderTrack: 'bg-pale-blue',
    sliderFill: 'bg-main-blue',
    sliderThumb: '[&::-moz-range-thumb]:border-main-blue [&::-webkit-slider-thumb]:border-main-blue',
    resetButton: 'border-gray-blue bg-pale-blue text-main-blue hover:bg-gray-blue/30 active:bg-gray-blue/45',
    exportButton: 'border border-main-blue bg-main-blue/10 text-main-blue hover:bg-main-blue/10',
  },
}

function CategoryPage() {
  const { siteName } = Route.useParams()
  const { q = '', location: locationParam } = Route.useSearch()
  const { city, setCity } = useCity()
  const cityLocation = getCityLocation(city)
  const isProductRoute = useRouterState({ select: (state) => /\/sites\/[^/]+\/[^/]+/.test(state.location.pathname) })

  useEffect(() => {
    if (locationParam === undefined) return
    if (locationParam === cityLocation) return
    if (locationParam === '') {
      setCity(NO_CITY_OPTION)
      return
    }
    const fromPopular = getPopularCities().find((item) => item.label === locationParam)
    setCity(fromPopular ?? { id: 0, value: locationParam, label: locationParam })
  }, [locationParam, cityLocation, setCity])

  const location = locationParam !== undefined ? locationParam : cityLocation
  const queryClient = useQueryClient()
  const { data: priceData, isLoading } = usePriceSearch({ query: q, location })
  const site = priceData?.sites.find((item) => item.slug === siteName) ?? findSiteInYandexSearchCache(queryClient, siteName, q, location)
  const isExternal = site?.kind === 'other'

  if (isProductRoute) return <Outlet />

  if (isLoading && !site) {
    return (
      <div className="min-h-screen bg-white p-6">
        <div className="text-gray mx-auto flex max-w-7xl items-center justify-center gap-2 py-12">
          <LoadingSpinner size="sm" />
          <span>Загружаем товары…</span>
        </div>
        <ResultsSkeleton />
      </div>
    )
  }

  if (!site) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-white p-6">
        <h1 className="text-2xl font-semibold">Категория не найдена</h1>
        <Link to="/sites" search={{ q, location }} className="text-main-blue hover:underline">
          Вернуться к результатам
        </Link>
      </div>
    )
  }

  return <CategorySiteView key={`${siteName}-${q}`} site={site} q={q} location={location} external={isExternal} />
}

function CategorySiteView({ site, q, location, external = false }: { site: SiteResult; q: string; location: string; external?: boolean }) {
  const accent = siteAccent[site.kind]
  const availableMin = minProductPrice(site.products)
  const availableMax = maxProductPrice(site.products)
  const [minPrice, setMinPrice] = useState(availableMin)
  const [maxPrice, setMaxPrice] = useState(availableMax)
  const [sort, setSort] = useState<SortValue>('relevant')
  const [view, setView] = useState<ViewMode>('grid')
  const [localQuery, setLocalQuery] = useState('')
  const [selectedBrandIds, setSelectedBrandIds] = useState<Set<string>>(() => new Set())
  const brandOptions = useMemo(() => getBrandFilterOptions(site.products), [site.products])
  const priceFilterActive = minPrice !== availableMin || maxPrice !== availableMax
  const brandFilterActive = selectedBrandIds.size > 0
  const filtersActive = priceFilterActive || brandFilterActive

  const products = useMemo(() => {
    const filtered = filterProducts(site.products, minPrice, maxPrice)
    const byBrand = filterProductsByBrands(filtered, selectedBrandIds)
    const byKeywords = filterProductsByLocalSearch(byBrand, localQuery)
    return sortProducts(byKeywords, sort)
  }, [site.products, minPrice, maxPrice, selectedBrandIds, sort, localQuery])

  const toggleBrand = (brandId: string) => {
    setSelectedBrandIds((current) => {
      const next = new Set(current)
      if (next.has(brandId)) next.delete(brandId)
      else next.add(brandId)
      return next
    })
  }

  const resetFilters = () => {
    setMinPrice(availableMin)
    setMaxPrice(availableMax)
    setSelectedBrandIds(new Set())
  }

  return (
    <div className="min-h-screen bg-white">
      <header className="border-gray-blue/60 border-b bg-white px-4 py-3 sm:px-6">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 gap-y-2">
          <div className="flex min-w-0 flex-1 items-center gap-5">
            <Link to="/sites" search={{ q, location }} className="text-gray flex shrink-0 items-center hover:text-black" aria-label="Назад">
              <IoArrowBack size={20} />
            </Link>
            <SiteTitle site={site} className="shrink-0" />
            <span className="text-gray shrink-0">/</span>
            <span className="min-w-0 truncate font-semibold text-black">{q || 'Все товары'}</span>
            <span className={cn('shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium', accent.badge)}>{products.length} товаров</span>
          </div>

          <div className="w-full sm:ml-auto sm:w-fit">
            {products.length > 0 && (
              <button
                type="button"
                onClick={() => exportSiteProductsToCsv(site, products, { query: q })}
                className={cn('bg-pale-blue/45 hover:bg-pale-blue/70 flex cursor-pointer items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium text-black transition-colors', accent.exportButton)}
              >
                <IoDownloadOutline className="shrink-0" size={18} aria-hidden />
                <span className="whitespace-nowrap">Экспорт</span>
              </button>
            )}
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl lg:grid-cols-[248px_1fr]">
        <aside className="border-gray-blue/60 border-b bg-white p-4 sm:p-5 lg:sticky lg:top-0 lg:h-[calc(100vh-57px)] lg:overflow-y-auto lg:border-r lg:border-b-0">
          <div className="space-y-6 pt-4">
            <div className="space-y-3">
              <p className="font-medium text-black">Цена, ₽</p>
              <PriceRangeSlider
                min={availableMin}
                max={availableMax}
                valueMin={minPrice}
                valueMax={maxPrice}
                trackClassName={accent.sliderTrack}
                fillClassName={accent.sliderFill}
                thumbClassName={accent.sliderThumb}
                presetRadioRingSelectedClassName={accent.sortRadioRing}
                presetRadioDotSelectedClassName={accent.sortRadioDot}
                onChange={({ min, max }) => {
                  setMinPrice(min)
                  setMaxPrice(max)
                }}
              />
              <p className="text-gray text-xs">
                {'Диапазон: '}
                {formatPrice(availableMin)} – {formatPrice(availableMax)}
              </p>
            </div>

            {brandOptions.length > 0 && (
              <>
                <hr className="border-gray-blue/60 border-t" />

                <div className="space-y-2">
                  <p className="font-medium text-black">Бренд</p>
                  <ul className="max-h-52 space-y-0.5 overflow-y-auto pr-1">
                    {brandOptions.map((option) => {
                      const selected = selectedBrandIds.has(option.id)

                      return (
                        <li key={option.id}>
                          <button
                            type="button"
                            onClick={() => toggleBrand(option.id)}
                            className="hover:bg-pale-blue/50 flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-1 py-1.5 text-left text-sm text-black transition-colors"
                            aria-pressed={selected}
                          >
                            <span className={cn('flex h-4 w-4 shrink-0 items-center justify-center rounded border-2 transition-colors', selected ? accent.sortRadioRing : 'border-gray-blue')} aria-hidden>
                              {selected && <span className={cn('h-2 w-2 rounded-xs', accent.sortRadioDot)} />}
                            </span>
                            <span className="min-w-0 flex-1 truncate">{option.label}</span>
                            <span className="text-gray shrink-0 text-xs tabular-nums">{option.count}</span>
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                </div>
              </>
            )}

            {filtersActive && (
              <button type="button" onClick={resetFilters} className={cn('w-full cursor-pointer rounded-xl px-4 py-2.5 text-sm font-medium transition-colors', accent.resetButton)}>
                Сбросить все
              </button>
            )}
          </div>
        </aside>

        <main className="min-w-0 bg-white p-4 sm:p-5">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="min-w-0 flex-1">
              <Input
                size="md"
                variant="outline"
                placeholder="Найти в результатах"
                value={localQuery}
                onChange={(e) => setLocalQuery(e.target.value)}
                leadingIcon={<IoSearch size={18} />}
                className="border-gray-blue/60 w-full rounded-3xl border bg-white text-black"
              />
            </div>

            <div className="flex shrink-0 items-center justify-between gap-3 sm:justify-end">
              <SortDropdown options={sortOptions} value={sort} onChange={(value) => setSort(value as SortValue)} radioRingSelectedClassName={accent.sortRadioRing} radioDotSelectedClassName={accent.sortRadioDot} />

              <div className="flex items-center gap-0.5 rounded-lg bg-white" role="group" aria-label="Вид списка">
                <button
                  type="button"
                  onClick={() => setView('grid')}
                  className={cn('transition-color hover:bg-pale-blue/50 cursor-pointer rounded-md p-2', view === 'grid' ? cn(accent.viewActive) : 'text-gray')}
                  aria-pressed={view === 'grid'}
                  aria-label="Плитка"
                >
                  <IoGridOutline size={20} />
                </button>
                <button
                  type="button"
                  onClick={() => setView('rows')}
                  className={cn('hover:bg-pale-blue/50 cursor-pointer rounded-md p-2 transition-colors', view === 'rows' ? cn(accent.viewActive) : 'text-gray')}
                  aria-pressed={view === 'rows'}
                  aria-label="Строки"
                >
                  <IoListOutline size={20} />
                </button>
              </div>
            </div>
          </div>

          <div className={view === 'grid' ? 'grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4' : 'flex flex-col gap-3'}>
            {products.map((product) => (
              <ProductCard key={product.id} product={product} siteSlug={site.slug} query={q} location={location} layout={view === 'rows' ? 'row' : 'tile'} surface="white" bordered={true} external={external} />
            ))}
            {products.length === 0 && <p className="text-gray col-span-full">Нет товаров по выбранным фильтрам.</p>}
          </div>
        </main>
      </div>
    </div>
  )
}

function filterProducts(products: Product[], min: number, max: number) {
  return products.filter((product) => {
    if (product.price < min) return false
    if (product.price > max) return false
    return true
  })
}

function sortProducts(products: Product[], sort: SortValue) {
  const sorted = [...products]
  if (sort === 'price-asc') return sorted.sort((a, b) => a.price - b.price)
  if (sort === 'price-desc') return sorted.sort((a, b) => b.price - a.price)
  if (sort === 'name-asc') return sorted.sort((a, b) => a.name.localeCompare(b.name, 'ru'))
  if (sort === 'name-desc') return sorted.sort((a, b) => b.name.localeCompare(a.name, 'ru'))
  return sorted
}

function minProductPrice(products: Product[]) {
  if (products.length === 0) return 0
  return Math.min(...products.map((product) => product.price))
}

function maxProductPrice(products: Product[]) {
  if (products.length === 0) return 0
  return Math.max(...products.map((product) => product.price))
}

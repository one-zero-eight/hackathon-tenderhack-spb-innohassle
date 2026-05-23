import { Link, Outlet, createFileRoute, useRouterState } from '@tanstack/react-router'
import { useEffect, useMemo, useState } from 'react'
import { IoArrowBack, IoGridOutline, IoListOutline, IoSearch } from 'react-icons/io5'
import { ProductCard } from '@/components/shared/ProductCard'
import PriceRangeSlider from '@/components/shared/PriceRangeSlider'
import { ResultsSkeleton } from '@/components/shared/ResultsSkeleton'
import SortDropdown from '@/components/shared/SortDropdown'
import Input from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useCity } from '@/hooks/useCity'
import { usePriceSearch } from '@/hooks/usePriceSearch'
import { cn } from '@/lib/cn'
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
  },
}

function CategoryPage() {
  const { siteName } = Route.useParams()
  const { q = '', location: locationParam } = Route.useSearch()
  const { city, setCity } = useCity()
  const isProductRoute = useRouterState({ select: (state) => /\/sites\/[^/]+\/[^/]+/.test(state.location.pathname) })

  useEffect(() => {
    if (locationParam && locationParam !== city.label) {
      setCity({ id: 0, value: locationParam, label: locationParam })
    }
  }, [locationParam, city.label, setCity])

  const location = city.label
  const { data: priceData, isLoading, isError } = usePriceSearch({ query: q, location })
  const sites = priceData?.sites ?? []
  const site = sites.find((item) => item.slug === siteName)

  if (isProductRoute) return <Outlet />

  if (isLoading) {
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

  if (isError || !site) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-white p-6">
        <h1 className="text-2xl font-semibold">Категория не найдена</h1>
        <Link to="/sites" search={{ q, location }} className="text-main-blue hover:underline">
          Вернуться к результатам
        </Link>
      </div>
    )
  }

  return <CategorySiteView key={`${siteName}-${q}`} site={site} q={q} location={location} />
}

function CategorySiteView({ site, q, location }: { site: SiteResult; q: string; location: string }) {
  const accent = siteAccent[site.kind]
  const availableMin = minProductPrice(site.products)
  const availableMax = maxProductPrice(site.products)
  const [minPrice, setMinPrice] = useState(availableMin)
  const [maxPrice, setMaxPrice] = useState(availableMax)
  const [sort, setSort] = useState<SortValue>('relevant')
  const [view, setView] = useState<ViewMode>('grid')
  const [localQuery, setLocalQuery] = useState('')
  const priceFilterActive = minPrice !== availableMin || maxPrice !== availableMax

  const products = useMemo(() => {
    const filtered = filterProducts(site.products, minPrice, maxPrice)
    const sorted = sortProducts(filtered, sort)
    const needle = localQuery.trim().toLowerCase()
    if (!needle) return sorted
    return sorted.filter((product) => product.name.toLowerCase().includes(needle))
  }, [site.products, minPrice, maxPrice, sort, localQuery])

  const resetFilters = () => {
    setMinPrice(availableMin)
    setMaxPrice(availableMax)
  }

  return (
    <div className="min-h-screen bg-white">
      <header className="border-gray-blue/60 border-b bg-white px-4 py-3 sm:px-6">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-3 gap-y-2">
          <div className="flex min-w-0 flex-1 items-center gap-5">
            <Link to="/sites" search={{ q, location }} className="text-gray flex shrink-0 items-center hover:text-black" aria-label="Назад">
              <IoArrowBack size={20} />
            </Link>
            {site.logo ? <img src={site.logo} alt={site.name} className="h-5 w-auto shrink-0 sm:h-6" /> : <span className="text-base font-semibold">{site.name}</span>}
            <span className="text-gray shrink-0">/</span>
            <span className="min-w-0 truncate font-semibold text-black">{q || 'Все товары'}</span>
            <span className={cn('shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium', accent.badge)}>{products.length} товаров</span>
          </div>

          <div className="w-full sm:ml-auto sm:w-72">
            <Input
              size="md"
              variant="outline"
              placeholder="Найти в результатах"
              value={localQuery}
              onChange={(e) => setLocalQuery(e.target.value)}
              leadingIcon={<IoSearch size={18} />}
              className="border-gray-blue rounded-xl border bg-white"
            />
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl lg:grid-cols-[248px_1fr]">
        <aside className="border-gray-blue/60 border-b bg-white p-4 sm:p-5 lg:sticky lg:top-0 lg:h-[calc(100vh-57px)] lg:overflow-y-auto lg:border-r lg:border-b-0">
          <div className="mb-5 flex items-center justify-between gap-2">
            <h2 className="text-sm font-bold tracking-wide text-black">ФИЛЬТРЫ</h2>
            {priceFilterActive && (
              <button type="button" onClick={resetFilters} className={cn('cursor-pointer text-sm', accent.link)}>
                Сбросить все
              </button>
            )}
          </div>

          <div className="border-gray-blue/40 space-y-3 border-t pt-4">
            <p className="font-medium text-black">Цена, ₽</p>
            <PriceRangeSlider
              min={availableMin}
              max={availableMax}
              valueMin={minPrice}
              valueMax={maxPrice}
              trackClassName={accent.sliderTrack}
              fillClassName={accent.sliderFill}
              thumbClassName={accent.sliderThumb}
              onChange={({ min, max }) => {
                setMinPrice(min)
                setMaxPrice(max)
              }}
            />
            <p className="text-gray text-xs">
              {'Диапозон: '}
              {formatPrice(availableMin)} – {formatPrice(availableMax)}
            </p>
          </div>
        </aside>

        <main className="min-w-0 bg-white p-4 sm:p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <SortDropdown options={sortOptions} value={sort} onChange={(value) => setSort(value as SortValue)} radioRingSelectedClassName={accent.sortRadioRing} radioDotSelectedClassName={accent.sortRadioDot} />

            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setView('grid')}
                className={cn('cursor-pointer rounded-lg p-2 transition-colors', view === 'grid' ? accent.viewActive : 'text-gray hover:bg-pale-blue/60')}
                aria-pressed={view === 'grid'}
                aria-label="Плитка"
              >
                <IoGridOutline size={20} />
              </button>
              <button
                type="button"
                onClick={() => setView('rows')}
                className={cn('cursor-pointer rounded-lg p-2 transition-colors', view === 'rows' ? accent.viewActive : 'text-gray hover:bg-pale-blue/60')}
                aria-pressed={view === 'rows'}
                aria-label="Строки"
              >
                <IoListOutline size={20} />
              </button>
            </div>
          </div>

          <div className={view === 'grid' ? 'grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4' : 'flex flex-col gap-3'}>
            {products.map((product) => (
              <ProductCard key={product.id} product={product} siteSlug={site.slug} query={q} location={location} layout={view === 'rows' ? 'row' : 'tile'} surface="white" bordered={true} />
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

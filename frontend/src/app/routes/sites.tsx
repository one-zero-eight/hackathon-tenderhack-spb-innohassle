import { Link, Outlet, createFileRoute, useNavigate, useRouterState } from '@tanstack/react-router'
import { IoSearch, IoStar, IoArrowBack, IoDownloadOutline } from 'react-icons/io5'
import CitySelect from '@/components/shared/CitySelect'
import SiteTitle from '@/components/shared/SiteTitle'
import { ProductCard, ViewAllCard } from '@/components/shared/ProductCard'
import { ResultsSkeleton } from '@/components/shared/ResultsSkeleton'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useCity } from '@/hooks/useCity'
import { useYandexSearch } from '@/hooks/useYandexSearch'
import { usePriceSearch, PRICE_SEARCH_LIMIT } from '@/hooks/usePriceSearch'
import { cn } from '@/lib/cn'
import { splitSiteResults } from '@/lib/mapSearchResults'
import { getCityLocation, getPopularCities, NO_CITY_OPTION } from '@/lib/geo'
import { getQueryCorrection } from '@/lib/queryCorrection'
import { countExportableProducts, exportSitesToCsv } from '@/lib/exportCsv'
import { formatPrice, formatSiteRating, type SiteResult } from '@/lib/searchResults'
import { useVisibleProductCount } from '@/lib/useVisibleProductCount'
import { memo, useEffect, useState } from 'react'

type SitesSearch = {
  q?: string
  strict?: boolean
  location?: string
}

export const Route = createFileRoute('/sites')({
  validateSearch: (search: Record<string, unknown>): SitesSearch => ({
    q: typeof search.q === 'string' ? search.q : '',
    strict: search.strict === true || search.strict === 'true' || search.strict === '1',
    location: typeof search.location === 'string' ? search.location : undefined,
  }),
  component: SitesPage,
})

const categoryTone: Record<SiteResult['kind'], string> = {
  ozon: 'border-blue-300 bg-blue-50 text-blue-700',
  wildberries: 'border-fuchsia-300 bg-fuchsia-50 text-fuchsia-700',
  yandex: 'border-orange-300 bg-orange-50 text-orange-700',
  other: 'border-gray-blue bg-gray-50 text-gray-700',
}

function SitesPage() {
  const { q = '', strict = false, location: locationParam } = Route.useSearch()
  const { city, setCity } = useCity()
  const cityLocation = getCityLocation(city)
  const location = locationParam !== undefined ? locationParam : cityLocation
  const isCategoryRoute = useRouterState({ select: (state) => state.location.pathname !== '/sites' })
  const navigate = useNavigate()
  const [query, setQuery] = useState(q)
  const [correctionHidden, setCorrectionHidden] = useState(false)

  const hasQuery = q.trim().length > 0
  const { data: priceData, isLoading, isError, error } = usePriceSearch({ query: q, location, bypassSpellchecker: strict })
  const sites = priceData?.sites ?? []
  const effectiveQuery = priceData?.effectiveQuery ?? q.trim()
  const correction = priceData ? getQueryCorrection(q, priceData.fixedQuery, strict) : null
  const streamEnabled = hasQuery && q.trim().length > 0
  const { sites: otherSiteResults, loading: otherLoading, error: otherError } = useYandexSearch(q, location, streamEnabled)

  useEffect(() => {
    setQuery(q)
  }, [q])

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

  useEffect(() => {
    setCorrectionHidden(false)
  }, [q, strict])

  if (isCategoryRoute) return <Outlet />

  const { main: mainSiteResults } = splitSiteResults(sites)
  const hasMainProducts = mainSiteResults.some((site) => site.products.length > 0)
  const hasOtherProducts = otherSiteResults.some((site) => site.products.length > 0)
  const showMarketplaceSkeleton = isLoading && !hasMainProducts
  const showMarketplaceStreaming = isLoading && hasMainProducts
  const showEmpty = hasQuery && !isLoading && !otherLoading && !isError && !otherError && !hasMainProducts && !hasOtherProducts
  const allSitesForExport = [...mainSiteResults, ...otherSiteResults]
  const exportableCount = countExportableProducts(allSitesForExport)

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    void navigate({ to: '/sites', search: { q: query.trim(), location } })
  }

  return (
    <div className="min-h-screen bg-white px-4 py-12 sm:px-6">
      <header className="mx-auto mb-8 max-w-7xl">
        <div className="mb-3 flex justify-between">
          <Link to="/search" className="flex items-center gap-2 hover:underline">
            <IoArrowBack size={20} /> Назад
          </Link>
          <div className="relative z-10">
            <CitySelect
              className="rounded-xl bg-white/80 backdrop-blur-sm"
              onCityChange={(picked) => {
                void navigate({
                  to: '/sites',
                  search: { q, strict: strict || undefined, location: getCityLocation(picked) },
                  replace: true,
                })
              }}
            />
          </div>
        </div>
        <form onSubmit={submitSearch} className="flex w-full flex-col rounded-full sm:flex-row sm:items-stretch">
          <Input size="md" variant="fill" value={query} onChange={(e) => setQuery(e.target.value)} leadingIcon={<IoSearch size={20} />} className="flex flex-1 rounded-l-full border-r-0" />
          <Button type="submit" variant="primary" size="sm" disabled={isLoading} className="border-dark-red shrink-0 self-center rounded-r-full sm:self-stretch">
            {isLoading ? <LoadingSpinner className="text-white" /> : 'Поиск'}
          </Button>
        </form>
        {correction && !correctionHidden && (
          <div className="text-gray mt-3 text-base">
            <p>
              Показаны результаты по запросу{' '}
              <button type="button" onClick={() => setCorrectionHidden(true)} className="text-main-blue cursor-pointer font-semibold italic hover:underline">
                {correction.displayedQuery}
              </button>
              .
            </p>
            <p className="text-sm">
              Искать вместо этого{' '}
              <Link to="/sites" search={{ q: correction.userQuery, strict: true, location }} className="text-main-blue hover:underline">
                {correction.userQuery}
              </Link>
            </p>
          </div>
        )}
      </header>

      <main className="mx-auto max-w-7xl">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-gray text-sm">Результаты поиска</p>
            {isLoading && !hasMainProducts ? <div className="bg-pale-blue mt-2 h-8 w-56 max-w-full animate-pulse rounded-lg" /> : <h1 className="text-2xl font-semibold text-black">{effectiveQuery || 'Все товары'}</h1>}
          </div>
          {exportableCount > 0 && (
            <Button type="button" variant="outline" size="sm" className="inline-flex items-center gap-2 rounded-lg" onClick={() => exportSitesToCsv(allSitesForExport, { query: effectiveQuery })}>
              <IoDownloadOutline size={18} />
              Экспорт ({exportableCount})
            </Button>
          )}
        </div>

        <div className="space-y-6 last:mb-0">
          {showMarketplaceSkeleton ? (
            <div className="space-y-6">
              <div className="text-gray flex items-center justify-center gap-2 py-2 text-sm">
                <LoadingSpinner size="sm" />
                <span>Ищем на Ozon, Wildberries и Yandex Market…</span>
              </div>
              <ResultsSkeleton />
            </div>
          ) : isError && !hasMainProducts ? (
            <p className="text-red py-4 text-center">{error instanceof Error ? error.message : 'Не удалось загрузить результаты маркетплейсов'}</p>
          ) : (
            <>
              {mainSiteResults.map((site) => (
                <SiteSection key={site.slug} site={site} query={effectiveQuery} location={location} pricesLoading={isLoading} productLimit={PRICE_SEARCH_LIMIT} />
              ))}
              {showMarketplaceStreaming && (
                <div className="text-gray flex items-center justify-center gap-2 py-2 text-sm">
                  <LoadingSpinner size="sm" />
                  <span>Загружаем ещё товары с маркетплейсов…</span>
                </div>
              )}
            </>
          )}

          {hasQuery && (
            <>
              {/* <div className="flex items-center gap-4 py-6">
                <div className="bg-gray-blue h-px flex-1" aria-hidden />
                <h2 className="shrink-0 text-xl font-semibold text-black">Другие источники</h2>
                <div className="bg-gray-blue h-px flex-1" aria-hidden />
              </div> */}

              {otherLoading && otherSiteResults.length === 0 && (
                <div className="text-gray flex items-center justify-center gap-2 py-4 text-sm">
                  <LoadingSpinner size="sm" />
                  <span>Ищем на других сайтах…</span>
                </div>
              )}

              {otherError && otherSiteResults.length === 0 && <p className="text-gray py-4 text-center text-sm">{otherError instanceof Error ? otherError.message : 'Не удалось загрузить другие источники'}</p>}

              {otherSiteResults.map((site) => (
                <SiteSection key={site.slug} site={site} query={effectiveQuery} location={location} external pricesLoading={otherLoading} />
              ))}

              {otherLoading && otherSiteResults.length > 0 && (
                <div className="text-gray flex items-center justify-center gap-2 py-2 text-sm">
                  <LoadingSpinner size="sm" />
                  <span>Обновляем результаты…</span>
                </div>
              )}
            </>
          )}

          {showEmpty && <p className="text-gray py-8 text-center">Ничего не найдено</p>}
        </div>
      </main>
    </div>
  )
}

function medianPrice(prices: number[]): number | null {
  if (prices.length === 0) return null
  const sorted = [...prices].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  if (sorted.length % 2 === 0) {
    return Math.round((sorted[mid - 1] + sorted[mid]) / 2)
  }
  return sorted[mid]
}

function SitePriceStat({ label, value, loading = false, className }: { label?: string; value?: number | null; loading?: boolean; className?: string }) {
  return (
    <div className={cn('flex shrink-0 flex-col items-center justify-center rounded-2xl bg-white px-3.5 py-2', className)}>
      {label && <p className="text-gray text-[11px] font-medium tracking-wide uppercase">{label}</p>}
      {loading ? (
        <div className="mt-1 flex justify-center">
          <LoadingSpinner size="sm" className="text-gray" />
        </div>
      ) : value != null ? (
        <p className="mt-0.5 text-base leading-tight font-semibold text-nowrap text-black tabular-nums">{formatPrice(value)}</p>
      ) : null}
    </div>
  )
}

function siteSectionPropsEqual(
  prev: { site: SiteResult; query: string; location: string; external?: boolean; pricesLoading?: boolean; productLimit?: number },
  next: { site: SiteResult; query: string; location: string; external?: boolean; pricesLoading?: boolean; productLimit?: number },
) {
  return (
    prev.site.slug === next.site.slug &&
    prev.site.products.length === next.site.products.length &&
    prev.site.sourceComplete === next.site.sourceComplete &&
    prev.site.rating === next.site.rating &&
    prev.site.reviewsLabel === next.site.reviewsLabel &&
    prev.site.error === next.site.error &&
    prev.pricesLoading === next.pricesLoading &&
    prev.productLimit === next.productLimit &&
    prev.query === next.query &&
    prev.location === next.location &&
    prev.external === next.external
  )
}

const SiteSection = memo(function SiteSection({
  site,
  query,
  location,
  external = false,
  pricesLoading = false,
  productLimit,
}: {
  site: SiteResult
  query: string
  location: string
  external?: boolean
  pricesLoading?: boolean
  productLimit?: number
}) {
  const visibleCount = useVisibleProductCount()
  const products = site.products.slice(0, visibleCount)
  const pricedProducts = site.products.filter((product) => product.price > 0)
  const prices = pricedProducts.map((product) => product.price)
  const medianProductPrice = medianPrice(prices)
  const averageProductPrice = prices.length > 0 ? Math.round(prices.reduce((sum, price) => sum + price, 0) / prices.length) : null
  const statsLoading =
    !external && pricesLoading && (productLimit == null ? true : site.products.length < productLimit && !site.sourceComplete)
  const showPriceStats = external ? pricedProducts.length > 0 : statsLoading || pricedProducts.length > 1
  const showViewAll = !external || site.products.length > 5

  if (site.error && site.products.length === 0) {
    return (
      <section className={cn('rounded-4xl border p-4 px-7', categoryTone[site.kind])}>
        <SiteTitle key={site.slug} site={site} />
        <p className="mt-2 text-sm opacity-80">{site.error}</p>
      </section>
    )
  }

  if (site.products.length === 0) return null

  return (
    <section className={cn('rounded-4xl border p-4', categoryTone[site.kind])}>
      <div className="mb-4 grid gap-3" style={{ gridTemplateColumns: `repeat(${visibleCount}, minmax(0, 1fr)) 5rem` }}>
        <div className="pt-1 pl-3" style={{ gridColumn: `span ${visibleCount - 2}` }}>
          <SiteTitle key={site.slug} site={site} className="col-span-full" />
          {(site.rating != null || site.reviewsLabel) && (
            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm">
              {site.rating != null && (
                <>
                  <span className="inline-flex items-center gap-1">
                    <IoStar className="text-orange shrink-0" size={16} aria-hidden />
                    <span className="font-medium">{formatSiteRating(site.rating)}</span>
                  </span>
                  {site.reviewsLabel && <span className="opacity-60">|</span>}
                </>
              )}
              {site.reviewsLabel && <span>{site.reviewsLabel}</span>}
            </div>
          )}
          <p className="mt-1 text-sm opacity-80">{site.products.length} товаров найдено</p>
        </div>
        {showPriceStats && (
          <>
            <SitePriceStat label="Средняя" value={averageProductPrice} loading={statsLoading} className="col-span-1" />
            <SitePriceStat label="Медиана" value={medianProductPrice} loading={statsLoading} className="col-span-1" />
          </>
        )}
      </div>
      <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${visibleCount}, minmax(0, 1fr)) 5rem` }}>
        {products.map((product) => (
          <ProductCard key={product.id} product={product} siteSlug={site.slug} query={query} location={location} layout="carousel" external={external} />
        ))}
        {showViewAll && <ViewAllCard siteSlug={site.slug} query={query} location={location} layout="carousel" compact />}
      </div>
    </section>
  )
}, siteSectionPropsEqual)

import { Link, createFileRoute } from '@tanstack/react-router'
import { AnalyticsPanel, DonutChart, HorizontalBarChart, RatingBars, SiteCompareChart, StatCard, VerticalBarChart } from '@/components/analytics/AnalyticsCharts'
import { ProductCard } from '@/components/shared/ProductCard'
import { ResultsSkeleton } from '@/components/shared/ResultsSkeleton'
import ExportCsvButton from '@/components/export/ExportCsvButton'
import Button from '@/components/ui/Button'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useCity } from '@/hooks/useCity'
import { useYandexSearch } from '@/hooks/useYandexSearch'
import { usePriceSearch } from '@/hooks/usePriceSearch'
import { getCityLocation } from '@/lib/geo'
import { splitSiteResults } from '@/lib/mapSearchResults'
import { formatPrice } from '@/lib/searchResults'
import { buildSearchAnalytics, hasAnalyticsData, KIND_COLORS, type AnalyticsProductRow } from '@/lib/searchAnalytics'
import { useVisibleProductCount } from '@/lib/useVisibleProductCount'
import { useMemo } from 'react'
import { IoArrowBack, IoStatsChart } from 'react-icons/io5'

type AnalyticsSearch = {
  q?: string
  strict?: boolean
  location?: string
}

export const Route = createFileRoute('/sites/analytics')({
  validateSearch: (search: Record<string, unknown>): AnalyticsSearch => ({
    q: typeof search.q === 'string' ? search.q : '',
    strict: search.strict === true || search.strict === 'true' || search.strict === '1',
    location: typeof search.location === 'string' ? search.location : undefined,
  }),
  component: SitesAnalyticsPage,
})

function SitesAnalyticsPage() {
  const { q = '', strict = false, location: locationParam } = Route.useSearch()
  const { city } = useCity()
  const cityLocation = getCityLocation(city)
  const location = locationParam !== undefined ? locationParam : cityLocation
  const trimmed = q.trim()
  const {
    data: priceData,
    isLoading: priceLoading,
    isError: priceError,
  } = usePriceSearch({
    query: q,
    location,
    bypassSpellchecker: strict,
    bypassRelevanceFilter: false,
  })
  const { sites: otherSites, loading: otherLoading } = useYandexSearch(q, location, trimmed.length > 0)

  const marketplaceSites = useMemo(() => splitSiteResults(priceData?.sites ?? []).main, [priceData?.sites])
  const allSites = useMemo(() => [...marketplaceSites, ...otherSites], [marketplaceSites, otherSites])

  const effectiveQuery = priceData?.effectiveQuery ?? trimmed
  const analytics = useMemo(() => buildSearchAnalytics(allSites, effectiveQuery), [allSites, effectiveQuery])
  const hasMarketplaceAnalytics = hasAnalyticsData(marketplaceSites)
  const hasAnyAnalytics = hasAnalyticsData(allSites)
  const showInitialLoading = trimmed.length > 0 && priceLoading && !hasMarketplaceAnalytics
  const showFatalError = priceError && !hasMarketplaceAnalytics && !priceLoading
  const locationForLinks = location ?? ''

  if (!trimmed) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-white p-6">
        <IoStatsChart className="text-main-blue/40" size={48} />
        <p className="text-gray text-center">Введите запрос на странице результатов, чтобы открыть аналитику.</p>
        <Link to="/search">
          <Button variant="primary">К поиску</Button>
        </Link>
      </div>
    )
  }

  return (
    <div className="from-pale-blue/30 min-h-screen bg-linear-to-b via-white to-white px-4 py-8 sm:px-6">
      <header className="mx-auto mb-8 max-w-7xl">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <Link to="/sites" search={{ q: effectiveQuery, location, strict: strict || undefined }} className="text-main-blue inline-flex items-center gap-2 text-sm font-medium hover:underline">
            <IoArrowBack size={18} />К результатам
          </Link>
          <div className="flex flex-wrap gap-2">
            <ExportCsvButton sites={allSites} query={effectiveQuery} />
          </div>
        </div>
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <p className="text-gray text-sm font-medium tracking-wide uppercase">Аналитика цен</p>
            <h1 className="text-main-blue mt-1 text-3xl font-bold tracking-tight sm:text-4xl">{effectiveQuery}</h1>
          </div>
          {(showInitialLoading || (otherLoading && otherSites.length === 0 && hasMarketplaceAnalytics)) && (
            <div className="text-gray flex items-center gap-2 text-sm">
              <LoadingSpinner size="sm" />
              {showInitialLoading ? 'Загружаем маркетплейсы…' : 'Догружаем другие источники…'}
            </div>
          )}
        </div>
      </header>

      {showFatalError ? (
        <p className="text-red mx-auto max-w-7xl text-center">Не удалось загрузить данные маркетплейсов для аналитики.</p>
      ) : showInitialLoading ? (
        <div className="mx-auto max-w-7xl">
          <ResultsSkeleton />
        </div>
      ) : !hasAnyAnalytics ? (
        <p className="text-gray mx-auto max-w-7xl text-center">Нет товаров с ценами для построения графиков.</p>
      ) : (
        <main className="mx-auto max-w-7xl space-y-6">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Товаров с ценой" value={String(analytics.summary.pricedCount)} hint={`из ${analytics.summary.productCount} найденных`} />
            <StatCard label="Минимальная цена" value={analytics.summary.minPrice != null ? formatPrice(analytics.summary.minPrice) : '—'} accent="text-green" />
            <StatCard label="Средняя цена" value={analytics.summary.avgPrice != null ? formatPrice(analytics.summary.avgPrice) : '—'} />
            <StatCard label="Медиана" value={analytics.summary.medianPrice != null ? formatPrice(analytics.summary.medianPrice) : '—'} />
            <StatCard label="Максимум" value={analytics.summary.maxPrice != null ? formatPrice(analytics.summary.maxPrice) : '—'} accent="text-red" />
            <StatCard label="Разброс цен" value={analytics.summary.spread != null ? formatPrice(analytics.summary.spread) : '—'} hint="макс − мин" />
            <StatCard label="Источников" value={String(analytics.summary.siteCount)} hint={`${analytics.summary.marketplaceSites} маркетплейса · ${analytics.summary.otherSites} других`} />
            {analytics.summary.discountCount > 0 && (
              <StatCard label="Со скидкой" value={String(analytics.summary.discountCount)} hint={analytics.summary.avgDiscountPct != null ? `ср. −${analytics.summary.avgDiscountPct}%` : undefined} accent="text-orange" />
            )}
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <AnalyticsPanel title="Доля по площадкам" subtitle="Распределение товаров с ценой">
              <DonutChart items={analytics.byKind} />
            </AnalyticsPanel>
            <AnalyticsPanel title="Распределение цен" subtitle="Гистограмма по диапазонам">
              <VerticalBarChart items={analytics.priceHistogram} />
            </AnalyticsPanel>
          </div>

          <div className="flex flex-col gap-6 lg:flex-row">
            <AnalyticsPanel title="Средняя цена по источнику" subtitle="Сравнение площадок" className="min-w-0 flex-1">
              <HorizontalBarChart
                items={analytics.bySite.map((row) => ({
                  id: row.slug,
                  label: row.name,
                  value: row.avgPrice ?? 0,
                  color: KIND_COLORS[row.kind],
                }))}
                valueFormat="price"
              />
            </AnalyticsPanel>
            <AnalyticsPanel title="Диапазон цен по магазину" subtitle="Минимум, максимум и медиана" className="min-w-0 flex-1">
              <SiteCompareChart
                rows={analytics.bySite.map((row) => ({
                  name: row.name,
                  minPrice: row.minPrice!,
                  maxPrice: row.maxPrice!,
                  medianPrice: row.medianPrice!,
                  color: KIND_COLORS[row.kind],
                }))}
              />
            </AnalyticsPanel>
          </div>

          <div className="flex flex-col gap-6">
            <AnalyticsTopProducts title="Минимальные цены" subtitle="Самые дешёвые предложения в выдаче" items={analytics.topCheapest} query={effectiveQuery} location={locationForLinks} />
            <AnalyticsTopProducts title="Максимальные цены" subtitle="Самые дорогие предложения в выдаче" items={analytics.topExpensive} query={effectiveQuery} location={locationForLinks} />
          </div>

          {analytics.ratedSites.length > 0 && (
            <AnalyticsPanel title="Рейтинг магазинов" subtitle="По данным выдачи">
              <RatingBars items={analytics.ratedSites} />
            </AnalyticsPanel>
          )}
        </main>
      )}
    </div>
  )
}

function AnalyticsTopProducts({ title, subtitle, items, query, location }: { title: string; subtitle: string; items: AnalyticsProductRow[]; query: string; location: string }) {
  const visibleCount = useVisibleProductCount()
  const columns = Math.min(visibleCount, Math.max(items.length, 1))
  const products = items.slice(0, visibleCount)

  if (products.length === 0) {
    return (
      <AnalyticsPanel title={title} subtitle={subtitle}>
        <p className="text-gray text-sm">Нет товаров для отображения</p>
      </AnalyticsPanel>
    )
  }

  return (
    <section className="border-gray-blue/60 rounded-4xl border bg-white p-4 shadow-sm">
      <div className="mb-4 pl-1">
        <h2 className="text-lg font-semibold text-black">{title}</h2>
        <p className="text-gray mt-0.5 text-sm">{subtitle}</p>
      </div>
      <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>
        {products.map((item) => (
          <ProductCard
            key={item.id}
            product={{ id: item.id, name: item.name, price: item.price, imageUrl: item.imageUrl, url: item.url }}
            siteSlug={item.siteSlug}
            query={query}
            location={location}
            layout="carousel"
            external={item.kind === 'other'}
            sourceName={item.siteName}
          />
        ))}
      </div>
    </section>
  )
}

import { Link, Outlet, createFileRoute, useNavigate, useRouterState } from '@tanstack/react-router'
import { IoSearch, IoStar, IoArrowBack } from 'react-icons/io5'
import CitySelect from '@/components/shared/CitySelect'
import { ProductCard, ViewAllCard } from '@/components/shared/ProductCard'
import { ResultsSkeleton } from '@/components/shared/ResultsSkeleton'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useCity } from '@/hooks/useCity'
import { useYandexSearchExtended } from '@/hooks/useYandexSearchExtended'
import { usePriceSearch } from '@/hooks/usePriceSearch'
import { cn } from '@/lib/cn'
import { splitSiteResults } from '@/lib/mapSearchResults'
import { getQueryCorrection, getResultsQuery } from '@/lib/queryCorrection'
import { formatPrice, formatSiteRating, type SiteResult } from '@/lib/searchResults'
import { useVisibleProductCount } from '@/lib/useVisibleProductCount'
import { useEffect, useState } from 'react'

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
  yandex: 'border-yellow-300 bg-yellow-50 text-yellow-700',
  other: 'border-gray-blue bg-gray-50 text-gray-700',
}

const SHOW_SEARCH_SUGGESTION = true

function SitesPage() {
  const { q = '', strict = false, location: locationParam } = Route.useSearch()
  const { city, setCity } = useCity()
  const location = city.label
  const correction = getQueryCorrection(q, strict, SHOW_SEARCH_SUGGESTION)
  const resultsQuery = getResultsQuery(q, strict, SHOW_SEARCH_SUGGESTION)
  const isCategoryRoute = useRouterState({ select: (state) => state.location.pathname !== '/sites' })
  const navigate = useNavigate()
  const [query, setQuery] = useState(q)
  const [correctionHidden, setCorrectionHidden] = useState(false)

  const hasQuery = resultsQuery.trim().length > 0
  const { data: sites = [], isLoading, isError, error } = usePriceSearch({ query: resultsQuery, location })
  const { sites: otherSiteResults, loading: otherLoading, error: otherError } = useYandexSearchExtended(resultsQuery, location, hasQuery)

  useEffect(() => {
    setQuery(q)
  }, [q])

  useEffect(() => {
    if (locationParam && locationParam !== city.label) {
      setCity({ id: 0, value: locationParam, label: locationParam })
    }
  }, [locationParam, city.label, setCity])

  useEffect(() => {
    setCorrectionHidden(false)
  }, [q, strict])

  if (isCategoryRoute) return <Outlet />

  const { main: mainSiteResults } = splitSiteResults(sites)
  const hasMainProducts = mainSiteResults.some((site) => site.products.length > 0)
  const hasOtherProducts = otherSiteResults.some((site) => site.products.length > 0)
  const showEmpty =
    hasQuery && !isLoading && !otherLoading && !isError && !otherError && !hasMainProducts && !hasOtherProducts

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    void navigate({ to: '/sites', search: { q: query.trim(), location } })
  }

  return (
    <div className="min-h-screen bg-white px-4 py-12 sm:px-6">
      <header className="mx-auto mb-8 max-w-7xl">
        <div className="mb-3 flex justify-between">
          <Link to="/" className="flex items-center gap-2 hover:underline">
            <IoArrowBack size={20} /> Назад
          </Link>
          <CitySelect className="w-44 sm:w-52" />
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
        <div className="mb-5">
          <p className="text-gray text-sm">Результаты поиска · {location}</p>
          {isLoading ? <div className="bg-pale-blue mt-2 h-8 w-56 max-w-full animate-pulse rounded-lg" /> : <h1 className="text-2xl font-semibold text-black">{resultsQuery || 'Все товары'}</h1>}
        </div>

        <div className="space-y-6 last:mb-0">
          {isLoading ? (
            <div className="space-y-6">
              <div className="text-gray flex items-center justify-center gap-2 py-2 text-sm">
                <LoadingSpinner size="sm" />
                <span>Ищем на Ozon, Wildberries и Yandex Market…</span>
              </div>
              <ResultsSkeleton />
            </div>
          ) : isError ? (
            <p className="text-red py-4 text-center">{error instanceof Error ? error.message : 'Не удалось загрузить результаты маркетплейсов'}</p>
          ) : (
            mainSiteResults.map((site) => <SiteSection key={site.slug} site={site} query={resultsQuery} location={location} />)
          )}

          {hasQuery && (
            <>
              <div className="flex items-center gap-4 py-6">
                <div className="bg-gray-blue h-px flex-1" aria-hidden />
                <h2 className="shrink-0 text-xl font-semibold text-black">Другие источники</h2>
                <div className="bg-gray-blue h-px flex-1" aria-hidden />
              </div>

              {otherLoading && otherSiteResults.length === 0 && (
                <div className="text-gray flex items-center justify-center gap-2 py-4 text-sm">
                  <LoadingSpinner size="sm" />
                  <span>Ищем на других сайтах…</span>
                </div>
              )}

              {otherError && otherSiteResults.length === 0 && (
                <p className="text-gray py-4 text-center text-sm">
                  {otherError instanceof Error ? otherError.message : 'Не удалось загрузить другие источники'}
                </p>
              )}

              {otherSiteResults.map((site) => (
                <SiteSection key={site.slug} site={site} query={resultsQuery} location={location} external />
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

function SiteSection({ site, query, location, external = false }: { site: SiteResult; query: string; location: string; external?: boolean }) {
  const visibleCount = useVisibleProductCount()
  const products = site.products.slice(0, visibleCount)
  const averagePrice = site.products.length > 0 ? Math.round(site.products.reduce((sum, product) => sum + product.price, 0) / site.products.length) : null

  if (site.error && site.products.length === 0) {
    return (
      <section className={cn('rounded-3xl border p-4', categoryTone[site.kind])}>
        <h2 className="text-xl font-semibold">{site.name}</h2>
        <p className="mt-2 text-sm opacity-80">{site.error}</p>
      </section>
    )
  }

  if (site.products.length === 0) return null

  return (
    <section className={cn('rounded-3xl border p-4', categoryTone[site.kind])}>
      <div className="mb-4 flex items-start justify-between gap-3 px-3 pt-1">
        <div>
          <h2 className="text-xl font-semibold">{site.name}</h2>
          {site.rating != null && (
            <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm">
              <span className="inline-flex items-center gap-1">
                <IoStar className="text-orange shrink-0" size={16} aria-hidden />
                <span className="font-medium">{formatSiteRating(site.rating)}</span>
              </span>
              <span className="opacity-60">|</span>
              {site.reviewsLabel && <span>{site.reviewsLabel}</span>}
            </div>
          )}
          <p className="mt-1 text-sm opacity-80">{site.products.length} товаров найдено</p>
        </div>
        {averagePrice != null && (
          <div className="shrink-0 text-right text-black">
            <p className="text-sm opacity-80">Средняя цена:</p>
            <p className="text-lg font-semibold">~{formatPrice(averagePrice)}</p>
          </div>
        )}
      </div>
      <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${visibleCount + 1}, minmax(0, 1fr))` }}>
        {products.map((product) => (
          <ProductCard key={product.id} product={product} siteSlug={site.slug} query={query} location={location} layout="carousel" external={external} />
        ))}
        {!external && <ViewAllCard siteSlug={site.slug} query={query} location={location} layout="carousel" />}
      </div>
    </section>
  )
}

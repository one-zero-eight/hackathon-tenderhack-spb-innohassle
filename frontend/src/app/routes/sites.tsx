import { Link, Outlet, createFileRoute, useNavigate, useRouterState } from '@tanstack/react-router'
import { IoSearch, IoStar } from 'react-icons/io5'
import { ProductCard, ViewAllCard } from '@/components/shared/ProductCard'
import { ResultsSkeleton } from '@/components/shared/ResultsSkeleton'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { cn } from '@/lib/cn'
import { formatPrice, formatSiteRating, mainSiteResults, otherSiteResults, type SiteResult } from '@/lib/searchResults'
import { getQueryCorrection, getResultsQuery } from '@/lib/queryCorrection'
import { SEARCH_LOADING_MS } from '@/lib/searchLoading'
import { useVisibleProductCount } from '@/lib/useVisibleProductCount'
import { useEffect, useState } from 'react'

type SitesSearch = {
  q?: string
  strict?: boolean
}

export const Route = createFileRoute('/sites')({
  validateSearch: (search: Record<string, unknown>): SitesSearch => ({
    q: typeof search.q === 'string' ? search.q : '',
    strict: search.strict === true || search.strict === 'true' || search.strict === '1',
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
  const { q = '', strict = false } = Route.useSearch()
  const correction = getQueryCorrection(q, strict, SHOW_SEARCH_SUGGESTION)
  const resultsQuery = getResultsQuery(q, strict, SHOW_SEARCH_SUGGESTION)
  const isCategoryRoute = useRouterState({ select: (state) => state.location.pathname !== '/sites' })
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState(q)
  const [correctionHidden, setCorrectionHidden] = useState(false)

  useEffect(() => {
    setLoading(true)
    const timer = setTimeout(() => setLoading(false), SEARCH_LOADING_MS)
    return () => clearTimeout(timer)
  }, [q, strict])

  useEffect(() => {
    setQuery(q)
  }, [q])

  useEffect(() => {
    setCorrectionHidden(false)
  }, [q, strict])

  if (isCategoryRoute) return <Outlet />

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    void navigate({ to: '/sites', search: { q: query.trim() } })
  }

  return (
    <div className="min-h-screen bg-white px-4 py-12 sm:px-6">
      <header className="mx-auto mb-8 max-w-7xl">
        <form onSubmit={submitSearch} className="flex w-full flex-col rounded-full sm:flex-row sm:items-stretch">
          <Input size="md" variant="fill" value={query} onChange={(e) => setQuery(e.target.value)} leadingIcon={<IoSearch size={20} />} className="flex flex-1 rounded-l-full border-r-0" />
          <Button type="submit" variant="primary" size="sm" disabled={loading} className="border-dark-red shrink-0 self-center rounded-r-full sm:self-stretch">
            {loading ? <LoadingSpinner size="sm" className="text-white" /> : 'Поиск'}
          </Button>
        </form>
        {correction && !correctionHidden && (
          <p className="text-gray mt-3 text-base">
            Показаны результаты по запросу{' '}
            <button type="button" onClick={() => setCorrectionHidden(true)} className="text-main-blue cursor-pointer font-semibold italic hover:underline">
              {correction.displayedQuery}
            </button>
            .<br />
            <div className="text-sm">
              Искать вместо этого{' '}
              <Link to="/sites" search={{ q: correction.userQuery, strict: true }} className="text-main-blue hover:underline">
                {correction.userQuery}
              </Link>
            </div>
          </p>
        )}
      </header>

      <main className="mx-auto max-w-7xl">
        <div className="mb-5">
          <p className="text-gray text-sm">Результаты поиска</p>
          {loading ? <div className="bg-pale-blue mt-2 h-8 w-56 max-w-full animate-pulse rounded-lg" /> : <h1 className="text-2xl font-semibold text-black">{resultsQuery || 'Все товары'}</h1>}
        </div>

        {loading ? (
          <div className="space-y-6">
            <div className="text-gray flex items-center justify-center gap-2 py-2 text-sm">
              <LoadingSpinner size="sm" />
              <span>Ищем товары…</span>
            </div>
            <ResultsSkeleton />
          </div>
        ) : (
          <div className="space-y-6 last:mb-0">
            {mainSiteResults.map((site) => (
              <SiteSection key={site.slug} site={site} query={resultsQuery} />
            ))}
            {otherSiteResults.length > 0 && (
              <>
                <div className="flex items-center gap-4 py-6">
                  <div className="bg-gray-blue h-px flex-1" aria-hidden />
                  <h2 className="shrink-0 text-xl font-semibold text-black">Другие источники</h2>
                  <div className="bg-gray-blue h-px flex-1" aria-hidden />
                </div>
                {otherSiteResults.map((site) => (
                  <SiteSection key={site.slug} site={site} query={resultsQuery} />
                ))}
              </>
            )}
          </div>
        )}
      </main>
    </div>
  )
}

function SiteSection({ site, query }: { site: SiteResult; query: string }) {
  const visibleCount = useVisibleProductCount()
  const products = site.products.slice(0, visibleCount)
  const averagePrice = Math.round(site.products.reduce((sum, product) => sum + product.price, 0) / site.products.length)

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
        <div className="shrink-0 text-right text-black">
          <p className="text-sm opacity-80">Средняя цена:</p>
          <p className="text-lg font-semibold">~{formatPrice(averagePrice)}</p>
        </div>
      </div>
      <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${visibleCount + 1}, minmax(0, 1fr))` }}>
        {products.map((product) => (
          <ProductCard key={product.id} product={product} siteSlug={site.slug} query={query} layout="carousel" />
        ))}
        <ViewAllCard siteSlug={site.slug} query={query} layout="carousel" />
      </div>
    </section>
  )
}

import { Link, createFileRoute } from '@tanstack/react-router'
import { useMemo } from 'react'
import { IoArrowBack, IoOpenOutline } from 'react-icons/io5'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useCity } from '@/hooks/useCity'
import { findProductInPriceSearchCache, usePriceSearch } from '@/hooks/usePriceSearch'
import { useQueryClient } from '@tanstack/react-query'
import { cn } from '@/lib/cn'
import { normalizeProductImageUrl } from '@/lib/normalizeProductImageUrl'
import { formatPrice, type SiteKind } from '@/lib/searchResults'

type ProductSearch = {
  q?: string
  location?: string
}

export const Route = createFileRoute('/sites/$siteName/$productId')({
  validateSearch: (search: Record<string, unknown>): ProductSearch => ({
    q: typeof search.q === 'string' ? search.q : '',
    location: typeof search.location === 'string' ? search.location : undefined,
  }),
  component: ProductPage,
})

const siteAccent: Record<
  SiteKind,
  {
    link: string
    imageFallback: string
    cta: string
    pricePill: string
  }
> = {
  ozon: {
    link: 'text-blue-600 hover:text-blue-700',
    imageFallback: 'bg-blue-50 text-blue-700',
    cta: 'bg-blue-600 text-white hover:bg-blue-700',
    pricePill: 'bg-green text-white',
  },
  wildberries: {
    link: 'text-fuchsia-600 hover:text-fuchsia-700',
    imageFallback: 'bg-fuchsia-50 text-fuchsia-700',
    cta: 'bg-fuchsia-600 text-white hover:bg-fuchsia-700',
    pricePill: 'bg-green text-white',
  },
  yandex: {
    link: 'text-yellow-700 hover:text-yellow-800',
    imageFallback: 'bg-yellow-50 text-yellow-800',
    cta: 'bg-yellow-500 text-white hover:bg-yellow-600',
    pricePill: 'bg-green text-white',
  },
  other: {
    link: 'text-main-blue hover:underline',
    imageFallback: 'bg-pale-blue text-gray',
    cta: 'bg-main-blue text-white hover:opacity-90',
    pricePill: 'bg-green text-white',
  },
}

function SpecRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[minmax(0,9rem)_1fr] gap-x-4 gap-y-1 text-sm sm:grid-cols-[minmax(0,10rem)_1fr]">
      <dt className="text-gray">{label}</dt>
      <dd className="text-black">{value}</dd>
    </div>
  )
}

function ProductPage() {
  const { siteName, productId } = Route.useParams()
  const { q = '', location: locationParam } = Route.useSearch()
  const { city } = useCity()
  const location = locationParam ?? city.label
  const searchParams = { query: q, location }
  const queryClient = useQueryClient()
  const cachedResult = findProductInPriceSearchCache(queryClient, siteName, productId, location)
  const { data: priceData, isLoading } = usePriceSearch(searchParams, !cachedResult)
  const result = useMemo(() => {
    if (cachedResult) return cachedResult
    const sites = priceData?.sites ?? []
    const site = sites.find((item) => item.slug === siteName)
    if (!site) return null
    const product = site.products.find((item) => item.id === productId)
    if (!product) return null
    return { site, product }
  }, [cachedResult, priceData, siteName, productId])

  if (!cachedResult && isLoading) {
    return (
      <div className="min-h-screen bg-white">
        <header className="border-gray-blue/60 border-b px-4 py-3 sm:px-6">
          <div className="text-gray mx-auto flex max-w-7xl items-center gap-2">
            <LoadingSpinner size="sm" />
            <span>Загружаем товар…</span>
          </div>
        </header>
      </div>
    )
  }

  if (!result) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-white p-6">
        <h1 className="text-2xl font-semibold">Товар не найден</h1>
        <Link to="/sites" search={{ q, location }} className="text-main-blue hover:underline">
          Вернуться к результатам
        </Link>
      </div>
    )
  }

  const { site, product } = result
  const accent = siteAccent[site.kind]
  const imageUrl = normalizeProductImageUrl(product.imageUrl)
  const hasDiscount = product.originalPrice != null && product.originalPrice > product.price
  const discountPercent = hasDiscount ? Math.round((1 - product.price / product.originalPrice!) * 100) : null

  return (
    <div className="min-h-screen bg-white">
      <header className="border-gray-blue/60 border-b bg-white px-4 py-3 sm:px-6">
        <div className="mx-auto flex h-[38px] max-w-7xl min-w-0 items-center gap-3 sm:gap-5">
          <Link to="/sites" search={{ q, location }} className="text-gray flex shrink-0 items-center hover:text-black" aria-label="Назад">
            <IoArrowBack size={20} />
          </Link>
          {site.logo ? <img src={site.logo} alt={site.name} className="h-5 w-auto shrink-0 sm:h-6" /> : <span className="shrink-0 text-base font-semibold">{site.name}</span>}
          <span className="text-gray shrink-0">/</span>
          <Link to="/sites/$siteName" params={{ siteName }} search={{ q, location }} className={cn('min-w-0 truncate font-medium hover:underline', accent.link)}>
            {q || 'Все товары'}
          </Link>
          <span className="text-gray shrink-0">/</span>
          <span className="min-w-0 truncate font-medium text-black" title={product.name}>
            {product.name}
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-5 sm:px-6 sm:py-6">
        <h1 className="mb-6 text-2xl leading-snug font-semibold text-balance text-black sm:text-3xl">{product.name}</h1>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem] xl:grid-cols-[minmax(0,1fr)_22rem]">
          <div className="min-w-0 space-y-6">
            <div className="border-gray-blue/60 overflow-hidden rounded-3xl border bg-white p-4 sm:p-6">
              {imageUrl ? (
                <img src={imageUrl} alt="" referrerPolicy="no-referrer" className="mx-auto aspect-square max-h-[36rem] w-full max-w-lg rounded-2xl object-contain object-center" />
              ) : (
                <div className={cn('mx-auto flex aspect-square w-full max-w-lg items-center justify-center rounded-2xl text-base font-medium', accent.imageFallback)}>Нет изображения</div>
              )}
            </div>

            <section className="border-gray-blue/60 rounded-3xl border bg-white p-5 sm:p-6">
              <h2 className="mb-4 text-lg font-semibold text-black">О товаре</h2>
              <dl className="space-y-3">
                <SpecRow label="Маркетплейс" value={site.name} />
                {product.brand && <SpecRow label="Бренд" value={product.brand} />}
              </dl>
            </section>
          </div>

          <aside className="lg:sticky lg:top-4 lg:self-start">
            <div className="border-gray-blue/60 space-y-4 rounded-3xl border bg-white p-5">
              {product.price > 0 ? (
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={cn('rounded-lg px-2.5 py-1 text-2xl font-semibold tabular-nums', accent.pricePill)}>{formatPrice(product.price)}</span>
                    {discountPercent != null && discountPercent > 0 && <span className="text-green text-sm font-medium">−{discountPercent}%</span>}
                  </div>
                  {hasDiscount && <p className="text-gray text-sm tabular-nums line-through">{formatPrice(product.originalPrice!)}</p>}
                </div>
              ) : (
                <p className="text-gray text-lg">Цена не указана</p>
              )}

              {product.url ? (
                <a href={product.url} target="_blank" rel="noopener noreferrer" className={cn('flex w-full items-center justify-center gap-2 rounded-xl px-4 py-3 text-sm font-medium transition-colors', accent.cta)}>
                  <IoOpenOutline size={18} aria-hidden />
                  Открыть на {site.name}
                </a>
              ) : (
                <p className="text-gray text-sm">Ссылка на товар недоступна</p>
              )}
            </div>
          </aside>
        </div>
      </main>
    </div>
  )
}

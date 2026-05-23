import { Link, createFileRoute } from '@tanstack/react-router'
import { useMemo } from 'react'
import { IoArrowBack } from 'react-icons/io5'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useCity } from '@/hooks/useCity'
import { usePriceSearch } from '@/hooks/usePriceSearch'
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

const imageTone: Record<SiteKind, string> = {
  ozon: 'bg-blue-100 text-blue-700',
  wildberries: 'bg-fuchsia-100 text-fuchsia-700',
  yandex: 'bg-yellow-100 text-yellow-700',
  other: 'bg-gray-100 text-gray-700',
}

const tone: Record<SiteKind, string> = {
  ozon: 'border-blue-300 bg-blue-50 text-blue-700',
  wildberries: 'border-fuchsia-300 bg-fuchsia-50 text-fuchsia-700',
  yandex: 'border-yellow-300 bg-yellow-50 text-yellow-700',
  other: 'border-gray-blue bg-gray-50 text-gray-700',
}

function ProductPage() {
  const { siteName, productId } = Route.useParams()
  const { q = '', location: locationParam } = Route.useSearch()
  const { city } = useCity()
  const location = locationParam ?? city.label
  const searchParams = { query: q, location }

  const { data: sites = [], isLoading } = usePriceSearch(searchParams)
  const result = useMemo(() => {
    const site = sites.find((item) => item.slug === siteName)
    if (!site) return null
    const product = site.products.find((item) => item.id === productId)
    if (!product) return null
    return { site, product }
  }, [sites, siteName, productId])

  if (isLoading) {
    return (
      <div className="text-gray flex min-h-screen items-center justify-center gap-2 bg-white">
        <LoadingSpinner size="sm" />
        <span>Загружаем товар…</span>
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
  const imageUrl = normalizeProductImageUrl(product.imageUrl)

  return (
    <div className="min-h-screen bg-white px-4 py-5 sm:px-6">
      <header className="mx-auto mb-6 flex max-w-4xl items-center justify-between gap-3">
        <Link to="/sites/$siteName" params={{ siteName }} search={{ q, location }} className="flex items-center gap-2 text-main-blue hover:underline">
          <IoArrowBack />
          Назад к {site.name}
        </Link>
        <p className="text-gray text-sm">{q || 'Все товары'}</p>
      </header>

      <main className="mx-auto max-w-4xl">
        <div className={cn('mb-6 inline-flex rounded-full border px-4 py-1.5 text-sm font-medium', tone[site.kind])}>{site.name}</div>

        <article className="border-gray-blue overflow-hidden rounded-3xl border bg-white">
          {imageUrl ? (
            <img src={imageUrl} alt="" referrerPolicy="no-referrer" className="mx-auto h-72 w-full max-w-md object-contain sm:h-96" />
          ) : (
            <div className={cn('flex h-72 items-center justify-center text-lg font-semibold sm:h-96', imageTone[site.kind])}>Нет изображения</div>
          )}
          <div className="space-y-4 p-6 sm:p-8">
            <h1 className="text-2xl font-semibold text-black sm:text-3xl">{product.name}</h1>
            {product.brand && <p className="text-gray text-sm">{product.brand}</p>}
            <div className="flex flex-wrap items-baseline gap-3">
              <p className="text-3xl font-semibold text-black">{formatPrice(product.price)}</p>
              {product.originalPrice != null && product.originalPrice > product.price && (
                <p className="text-gray text-lg line-through">{formatPrice(product.originalPrice)}</p>
              )}
            </div>
            {product.url && (
              <a href={product.url} target="_blank" rel="noreferrer" className="text-main-blue inline-flex text-sm font-medium hover:underline">
                Открыть на {site.name}
              </a>
            )}
          </div>
        </article>
      </main>
    </div>
  )
}

import { Link, createFileRoute } from '@tanstack/react-router'
import { IoArrowBack } from 'react-icons/io5'
import { cn } from '@/lib/cn'
import { formatPrice, getProduct, type SiteKind } from '@/lib/searchResults'

type ProductSearch = {
  q?: string
}

export const Route = createFileRoute('/sites/$siteName/$productId')({
  validateSearch: (search: Record<string, unknown>): ProductSearch => ({
    q: typeof search.q === 'string' ? search.q : '',
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
  const { q = '' } = Route.useSearch()
  const result = getProduct(siteName, productId)

  if (!result) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6">
        <h1 className="text-2xl font-semibold">Товар не найден</h1>
        <Link to="/sites" search={{ q }} className="text-main-blue hover:underline">
          Вернуться к результатам
        </Link>
      </div>
    )
  }

  const { site, product } = result

  return (
    <div className="min-h-screen bg-white px-4 py-5 sm:px-6">
      <header className="mx-auto mb-6 flex max-w-4xl items-center justify-between gap-3">
        <Link to="/sites/$siteName" params={{ siteName }} search={{ q }} className="flex items-center gap-2 text-main-blue hover:underline">
          <IoArrowBack />
          Назад к {site.name}
        </Link>
        <p className="text-sm text-gray">{q || 'Все товары'}</p>
      </header>

      <main className="mx-auto max-w-4xl">
        <div className={cn('mb-6 inline-flex rounded-full border px-4 py-1.5 text-sm font-medium', tone[site.kind])}>{site.name}</div>

        <article className="overflow-hidden rounded-3xl border border-gray-blue bg-white">
          <div className={cn('flex h-72 items-center justify-center text-lg font-semibold sm:h-96', imageTone[site.kind])}>Image</div>
          <div className="space-y-4 p-6 sm:p-8">
            <h1 className="text-2xl font-semibold text-black sm:text-3xl">{product.name}</h1>
            <p className="text-3xl font-semibold text-black">{formatPrice(product.price)}</p>
            <p className="text-sm text-gray">Данные получены с площадки {site.name}. Подключение к API будет добавлено позже.</p>
          </div>
        </article>
      </main>
    </div>
  )
}

import { Link } from '@tanstack/react-router'
import { IoArrowForward } from 'react-icons/io5'
import { cn } from '@/lib/cn'
import { formatPrice, type Product } from '@/lib/searchResults'

type CardLayout = 'carousel' | 'tile' | 'row'

type ProductCardProps = {
  product: Product
  siteSlug: string
  query?: string
  layout?: CardLayout
  surface?: 'white' | 'muted'
  bordered?: boolean
}

type ViewAllCardProps = {
  siteSlug: string
  query?: string
  layout?: CardLayout
}

function productLinkProps(siteSlug: string, product: Product, query: string) {
  return {
    to: '/sites/$siteName/$productId' as const,
    params: { siteName: siteSlug, productId: product.id },
    search: { q: query },
  }
}

function ProductImageSkeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn('bg-pale-blue aspect-square w-full animate-pulse rounded-xl', className)} />
}

export function ProductCard({ product, siteSlug, query = '', layout = 'carousel', surface = 'white', bordered = false }: ProductCardProps) {
  const link = productLinkProps(siteSlug, product, query)
  const cardBg = surface === 'muted' ? 'bg-pale-blue/35' : 'bg-white'
  const imageWrap = surface === 'muted' ? 'overflow-hidden rounded-xl bg-white' : 'block overflow-hidden rounded-xl bg-white'
  const cardBorder = bordered ? 'border border-gray-blue/60' : undefined

  if (layout === 'row') {
    return (
      <article className={cn('flex items-start overflow-hidden rounded-3xl p-2', cardBg, cardBorder)}>
        <Link {...link} className={cn('block w-28 shrink-0 sm:w-32', imageWrap)}>
          <ProductImageSkeleton />
        </Link>
        <div className="flex min-w-0 flex-1 flex-col justify-start gap-1 px-2 py-1 sm:px-3">
          <Link {...link} className="line-clamp-2 text-sm leading-snug font-medium text-black">
            {product.name}
          </Link>
          <Link {...link} className="text-lg leading-tight font-semibold text-black">
            {formatPrice(product.price)}
          </Link>
        </div>
      </article>
    )
  }

  return (
    <article className={cn('flex h-full min-w-0 flex-col rounded-3xl p-3', cardBg, cardBorder)}>
      <Link {...link} className={imageWrap}>
        <ProductImageSkeleton />
      </Link>

      <div className="flex min-w-0 flex-col gap-1 px-0.5 pt-2">
        <Link {...link} className="truncate text-base leading-tight font-semibold text-black">
          {formatPrice(product.price)}
        </Link>
        <Link {...link} className="line-clamp-2 text-sm leading-snug text-black">
          {product.name}
        </Link>
      </div>
    </article>
  )
}

export function ViewAllCard({ siteSlug, query = '', layout = 'carousel' }: ViewAllCardProps) {
  const isRow = layout === 'row'

  return (
    <Link
      to="/sites/$siteName"
      params={{ siteName: siteSlug }}
      search={{ q: query }}
      className={cn('flex min-w-0 items-center justify-center rounded-2xl bg-white text-black', isRow ? 'min-h-30 w-full p-4' : 'h-full min-h-0 flex-col gap-2 p-2', layout === 'tile' ? 'aspect-168/248 w-full' : undefined)}
    >
      <span className="flex items-center gap-2 text-sm font-semibold sm:text-base">
        Все
        <IoArrowForward size={20} />
      </span>
    </Link>
  )
}

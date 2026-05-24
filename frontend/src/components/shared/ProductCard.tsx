import { Link } from '@tanstack/react-router'
import { useState } from 'react'
import { IoArrowForward } from 'react-icons/io5'
import { cn } from '@/lib/cn'
import { normalizeProductImageUrl } from '@/lib/normalizeProductImageUrl'
import { formatPrice, type Product } from '@/lib/searchResults'

type CardLayout = 'carousel' | 'tile' | 'row'

type ProductCardProps = {
  product: Product
  siteSlug: string
  query?: string
  location?: string
  layout?: CardLayout
  surface?: 'white' | 'muted'
  bordered?: boolean
  external?: boolean
  sourceName?: string
}

type ViewAllCardProps = {
  siteSlug: string
  query?: string
  location?: string
  layout?: CardLayout
  compact?: boolean
}

function productLinkProps(siteSlug: string, product: Product, query: string, location?: string, external?: boolean) {
  if (external && product.url) {
    return { href: product.url, target: '_blank', rel: 'noopener noreferrer' } as const
  }

  return {
    to: '/sites/$siteName/$productId' as const,
    params: { siteName: siteSlug, productId: product.id },
    search: { q: query, location },
  }
}

function ProductLink({ product, siteSlug, query, location, external, className, children }: { product: Product; siteSlug: string; query: string; location?: string; external?: boolean; className?: string; children: React.ReactNode }) {
  const props = productLinkProps(siteSlug, product, query, location, external)

  if ('href' in props) {
    return (
      <a {...props} className={className}>
        {children}
      </a>
    )
  }

  return (
    <Link {...props} className={className}>
      {children}
    </Link>
  )
}

function ProductImageSkeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn('bg-pale-blue aspect-3/4 w-full animate-pulse rounded-xl', className)} />
}

function ProductImage({ product, className }: { product: Product; className?: string }) {
  const [failed, setFailed] = useState(false)
  const imageUrl = normalizeProductImageUrl(product.imageUrl)

  if (imageUrl && !failed) {
    return <img src={imageUrl} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} className={cn('h-full w-full object-cover object-center', className)} />
  }

  return <ProductImageSkeleton className={className} />
}

const imageFrameClass = 'block aspect-3/4 w-full overflow-hidden rounded-xl bg-white'

export function ProductCard({ product, siteSlug, query = '', location, layout = 'carousel', surface = 'white', bordered = false, external = false, sourceName }: ProductCardProps) {
  const cardBg = surface === 'muted' ? 'bg-pale-blue/35' : 'bg-white'
  const cardBorder = bordered ? 'border border-gray-blue/60' : undefined
  const showPrice = product.price > 0

  if (layout === 'row') {
    return (
      <article className={cn('flex items-start overflow-hidden rounded-3xl', cardBg, cardBorder)}>
        <ProductLink product={product} siteSlug={siteSlug} query={query} location={location} external={external} className={cn('m-3 block w-28 shrink-0 sm:w-32', imageFrameClass)}>
          <ProductImage product={product} />
        </ProductLink>
        <div className="flex min-w-0 flex-1 flex-col justify-start gap-1 px-2 py-5 sm:px-3">
          <ProductLink product={product} siteSlug={siteSlug} query={query} location={location} external={external} className="line-clamp-2 text-base leading-snug font-medium text-black">
            {product.name}
          </ProductLink>
          {showPrice && (
            <ProductLink product={product} siteSlug={siteSlug} query={query} location={location} external={external} className="text-lg leading-tight font-semibold text-black">
              {formatPrice(product.price)}
            </ProductLink>
          )}
        </div>
      </article>
    )
  }

  return (
    <article className={cn('flex h-full min-w-0 flex-col rounded-3xl p-3', cardBg, cardBorder)}>
      <ProductLink product={product} siteSlug={siteSlug} query={query} location={location} external={external} className={imageFrameClass}>
        <ProductImage product={product} />
      </ProductLink>

      <div className="flex min-w-0 flex-col gap-1 px-0.5 pt-2">
        {sourceName ? (
          <>
            <ProductLink product={product} siteSlug={siteSlug} query={query} location={location} external={external} className="line-clamp-2 text-sm leading-snug font-medium text-black">
              {product.name}
            </ProductLink>
            <p className="text-gray truncate text-xs">{sourceName}</p>
            {showPrice && (
              <ProductLink product={product} siteSlug={siteSlug} query={query} location={location} external={external} className="truncate text-base leading-tight font-semibold text-black">
                {formatPrice(product.price)}
              </ProductLink>
            )}
          </>
        ) : (
          <>
            {showPrice && (
              <ProductLink product={product} siteSlug={siteSlug} query={query} location={location} external={external} className="truncate text-base leading-tight font-semibold text-black">
                {formatPrice(product.price)}
              </ProductLink>
            )}
            <ProductLink product={product} siteSlug={siteSlug} query={query} location={location} external={external} className="line-clamp-2 text-sm leading-snug text-black">
              {product.name}
            </ProductLink>
          </>
        )}
      </div>
    </article>
  )
}

export function ViewAllCard({ siteSlug, query = '', location, layout = 'carousel', compact = false }: ViewAllCardProps) {
  const isRow = layout === 'row'

  return (
    <Link
      to="/sites/$siteName"
      params={{ siteName: siteSlug }}
      search={{ q: query, location }}
      className={cn(
        'group flex min-w-0 items-center justify-center rounded-2xl bg-white text-black',
        isRow ? 'min-h-30 w-full p-4' : 'h-full min-h-0 flex-col',
        compact ? 'p-1' : 'gap-2 p-2',
        layout === 'tile' ? 'aspect-168/248 w-full' : undefined,
      )}
    >
      <span className={cn('flex items-center gap-2 font-semibold', compact ? 'text-sm' : 'text-sm sm:text-base')}>
        <IoArrowForward size={compact ? 18 : 20} className="transition duration-200 group-hover:translate-x-1" />
      </span>
    </Link>
  )
}

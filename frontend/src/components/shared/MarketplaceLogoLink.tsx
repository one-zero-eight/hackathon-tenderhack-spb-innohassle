import { cn } from '@/lib/cn'
import { getMarketplaceUrl, type SiteResult } from '@/lib/searchResults'

type Props = {
  site: SiteResult
  className?: string
  imgClassName?: string
  fallbackClassName?: string
}

export default function MarketplaceLogoLink({ site, className, imgClassName, fallbackClassName }: Props) {
  const url = getMarketplaceUrl(site.kind)
  const content = site.logo ? <img src={site.logo} alt={site.name} className={imgClassName} /> : <span className={fallbackClassName}>{site.name}</span>

  if (url) {
    return (
      <a href={url} target="_blank" rel="noopener noreferrer" className={cn('inline-flex shrink-0 items-center', className)}>
        {content}
      </a>
    )
  }

  return <span className={cn('inline-flex min-w-0 items-center', className)}>{content}</span>
}

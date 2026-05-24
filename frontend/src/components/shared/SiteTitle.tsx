import MarketplaceLogoLink from '@/components/shared/MarketplaceLogoLink'
import { cn } from '@/lib/cn'
import type { SiteResult } from '@/lib/searchResults'
import { useState } from 'react'

function otherSourceFaviconUrl(hostname: string): string {
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(hostname)}&sz=128`
}

type SiteTitleProps = {
  site: SiteResult
  className?: string
}

export default function SiteTitle({ site, className }: SiteTitleProps) {
  const [faviconFailed, setFaviconFailed] = useState(false)

  if (site.kind !== 'other') {
    return <MarketplaceLogoLink site={site} className={className} imgClassName={cn('w-auto object-contain object-left', site.kind === 'ozon' ? 'h-5 max-w-[120px] sm:h-6' : 'h-6 max-w-[160px] sm:h-7')} />
  }

  const faviconSrc = site.logo ?? otherSourceFaviconUrl(site.name)

  return (
    <div className={cn('flex min-w-0 items-center gap-2', className)}>
      {!faviconFailed && <img src={faviconSrc} alt="" aria-hidden onError={() => setFaviconFailed(true)} className="h-5 w-5 shrink-0 rounded-sm object-contain" />}
      <h2 className="truncate text-xl font-semibold">{site.name}</h2>
    </div>
  )
}

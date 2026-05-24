import ExportCsvDialog from '@/components/export/ExportCsvDialog'
import Button from '@/components/ui/Button'
import { countExportableProducts } from '@/lib/exportCsv'
import type { SiteResult } from '@/lib/searchResults'
import { cn } from '@/lib/cn'
import { useState } from 'react'
import { IoDownloadOutline } from 'react-icons/io5'

type ExportCsvButtonProps = {
  sites: SiteResult[]
  query: string
  iconOnly?: boolean
  className?: string
}

export default function ExportCsvButton({ sites, query, iconOnly = false, className }: ExportCsvButtonProps) {
  const [open, setOpen] = useState(false)
  const exportableCount = countExportableProducts(sites)

  if (exportableCount === 0) return null

  return (
    <>
      <Button
        type="button"
        variant="outline"
        size="sm"
        aria-label="Экспорт в CSV"
        className={cn(
          iconOnly ? 'inline-flex size-10 shrink-0 items-center justify-center rounded-lg p-0' : 'inline-flex items-center gap-2 rounded-lg',
          className,
        )}
        onClick={() => setOpen(true)}
      >
        <IoDownloadOutline size={iconOnly ? 20 : 18} />
        {!iconOnly && 'Экспорт в CSV'}
      </Button>
      <ExportCsvDialog isOpen={open} onClose={() => setOpen(false)} sites={sites} query={query} />
    </>
  )
}

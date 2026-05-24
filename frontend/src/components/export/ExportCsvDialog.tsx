import { Dialog, DialogBackdrop, DialogPanel, DialogTitle } from '@headlessui/react'
import Button from '@/components/ui/Button'
import { countExportableProducts, exportSitesToCsv } from '@/lib/exportCsv'
import type { SiteResult } from '@/lib/searchResults'
import { useMemo, useState } from 'react'

type ExportCsvDialogProps = {
  isOpen: boolean
  onClose: () => void
  sites: SiteResult[]
  query: string
}

function ExportCsvDialogBody({ onClose, sites, query }: Omit<ExportCsvDialogProps, 'isOpen'>) {
  const exportableSites = useMemo(() => sites.filter((site) => site.products.length > 0), [sites])
  const [selectedSlugs, setSelectedSlugs] = useState(() => new Set(exportableSites.map((site) => site.slug)))

  const allSelected = exportableSites.length > 0 && exportableSites.every((site) => selectedSlugs.has(site.slug))
  const selectedProductCount = exportableSites.filter((site) => selectedSlugs.has(site.slug)).reduce((sum, site) => sum + site.products.length, 0)

  const toggleSite = (slug: string) => {
    setSelectedSlugs((prev) => {
      const next = new Set(prev)
      if (next.has(slug)) next.delete(slug)
      else next.add(slug)
      return next
    })
  }

  const handleExport = () => {
    const filtered = exportableSites.filter((site) => selectedSlugs.has(site.slug))
    if (exportSitesToCsv(filtered, { query })) onClose()
  }

  return (
    <DialogPanel className="flex max-h-[min(32rem,90vh)] w-full max-w-md flex-col rounded-2xl bg-white shadow-lg">
      <div className="border-gray-blue/40 border-b px-6 py-5">
        <DialogTitle className="text-lg font-semibold text-black">Экспорт в CSV</DialogTitle>
        <p className="text-gray mt-1 text-sm">Выберите источники для выгрузки</p>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">
        <div className="mb-3 flex items-center justify-between gap-2">
          <span className="text-gray text-sm">
            {selectedProductCount} из {countExportableProducts(exportableSites)} товаров
          </span>
          <button type="button" className="text-main-blue text-sm font-medium hover:underline" onClick={() => setSelectedSlugs(new Set(allSelected ? [] : exportableSites.map((site) => site.slug)))}>
            {allSelected ? 'Снять всё' : 'Выбрать всё'}
          </button>
        </div>

        <div className="border-gray-blue/60 overflow-hidden rounded-xl border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-gray-blue/60 bg-pale-blue/40 border-b text-left">
                <th className="w-10 px-3 py-2.5" aria-label="Выбрать" />
                <th className="px-3 py-2.5 font-medium text-black">Источник</th>
                <th className="px-3 py-2.5 text-right font-medium text-black">Товаров</th>
              </tr>
            </thead>
            <tbody>
              {exportableSites.map((site) => (
                <tr key={site.slug} className="border-gray-blue/40 hover:bg-pale-blue/25 cursor-pointer border-b last:border-b-0" onClick={() => toggleSite(site.slug)}>
                  <td className="px-3 py-2.5 align-middle" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      className="border-gray-blue text-main-blue size-4 rounded"
                      checked={selectedSlugs.has(site.slug)}
                      onChange={() => toggleSite(site.slug)}
                      aria-label={`Включить ${site.name}`}
                    />
                  </td>
                  <td className="px-3 py-2.5 align-middle font-medium text-black">{site.name}</td>
                  <td className="text-gray px-3 py-2.5 text-right align-middle tabular-nums">{site.products.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="border-gray-blue/40 flex justify-end gap-3 border-t px-6 py-4">
        <Button type="button" size="sm" variant="outline" onClick={onClose}>
          Отмена
        </Button>
        <Button type="button" size="sm" variant="primary" disabled={selectedProductCount === 0} onClick={handleExport}>
          Скачать CSV
        </Button>
      </div>
    </DialogPanel>
  )
}

export default function ExportCsvDialog({ isOpen, onClose, sites, query }: ExportCsvDialogProps) {
  return (
    <Dialog open={isOpen} onClose={onClose} className="relative z-50">
      <DialogBackdrop className="fixed inset-0 bg-black/30" />
      <div className="fixed inset-0 flex w-screen items-center justify-center p-4">
        {isOpen && <ExportCsvDialogBody sites={sites} query={query} onClose={onClose} />}
      </div>
    </Dialog>
  )
}

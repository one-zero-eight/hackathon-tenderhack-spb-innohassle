import type { Product, SiteResult } from '@/lib/searchResults'

const HEADERS = ['Источник', 'Название', 'Бренд', 'Цена', 'Ссылка'] as const

type CsvRow = [source: string, name: string, brand: string, price: string, url: string]

function escapeCsvField(value: string | number | null | undefined): string {
  if (value == null || value === '') return ''
  const str = String(value)
  if (/[",\n\r]/.test(str)) return `"${str.replace(/"/g, '""')}"`
  return str
}

function buildCsv(rows: readonly (readonly string[])[]): string {
  return rows.map((row) => row.map(escapeCsvField).join(',')).join('\r\n')
}

function sanitizeFilename(value: string): string {
  return (
    value
      .trim()
      .replace(/[^\w\u0400-\u04FF.-]+/gi, '-')
      .replace(/-+/g, '-')
      .slice(0, 80) || 'export'
  )
}

function formatExportDate(): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`
}

function downloadCsv(filename: string, content: string) {
  const blob = new Blob(['\uFEFF', content], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

function productToRow(product: Product, site: SiteResult): CsvRow {
  return [site.name, product.name, product.brand ?? '', product.price > 0 ? String(product.price) : '', product.url ?? '']
}

function buildProductRows(sites: SiteResult[]): (typeof HEADERS | CsvRow)[] {
  const rows: (typeof HEADERS | CsvRow)[] = [HEADERS]
  for (const site of sites) {
    for (const product of site.products) {
      rows.push(productToRow(product, site))
    }
  }
  return rows
}

export function countExportableProducts(sites: SiteResult[]): number {
  return sites.reduce((sum, site) => sum + site.products.length, 0)
}

export function exportSitesToCsv(sites: SiteResult[], { query }: { query: string }): boolean {
  const rows = buildProductRows(sites)
  if (rows.length <= 1) return false

  const name = sanitizeFilename(query || 'results')
  downloadCsv(`${name}-${formatExportDate()}.csv`, buildCsv(rows))
  return true
}

export function exportSiteProductsToCsv(site: SiteResult, products: Product[], { query }: { query: string }): boolean {
  if (products.length === 0) return false

  const rows: (typeof HEADERS | CsvRow)[] = [HEADERS]
  for (const product of products) {
    rows.push(productToRow(product, site))
  }

  const name = sanitizeFilename(`${site.slug}-${query || 'results'}`)
  downloadCsv(`${name}-${formatExportDate()}.csv`, buildCsv(rows))
  return true
}

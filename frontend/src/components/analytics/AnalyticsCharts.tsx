import { cn } from '@/lib/cn'
import { formatPrice } from '@/lib/searchResults'
import type { AnalyticsSegment } from '@/lib/searchAnalytics'

export function AnalyticsPanel({ title, subtitle, children, className }: { title: string; subtitle?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn('border-gray-blue/60 rounded-3xl border bg-white p-5 shadow-sm', className)}>
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-black">{title}</h2>
        {subtitle && <p className="text-gray mt-0.5 text-sm">{subtitle}</p>}
      </div>
      {children}
    </section>
  )
}

export function StatCard({ label, value, hint, accent }: { label: string; value: string; hint?: string; accent?: string }) {
  return (
    <div className="border-gray-blue/50 rounded-2xl border bg-white p-4">
      <p className="text-gray text-xs font-medium tracking-wide uppercase">{label}</p>
      <p className={cn('mt-1 text-2xl font-bold tabular-nums', accent ?? 'text-main-blue')}>{value}</p>
      {hint && <p className="text-gray mt-1 text-xs">{hint}</p>}
    </div>
  )
}

export function HorizontalBarChart({ items, valueFormat = 'number' }: { items: AnalyticsSegment[]; valueFormat?: 'number' | 'price' }) {
  const max = Math.max(...items.map((i) => i.value), 1)

  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item.id}>
          <div className="mb-1 flex items-center justify-between gap-2 text-sm">
            <span className="min-w-0 truncate font-medium text-black">{item.label}</span>
            <span className="text-gray shrink-0 tabular-nums">{valueFormat === 'price' ? formatPrice(item.value) : item.value}</span>
          </div>
          <div className="bg-pale-blue/60 h-2.5 overflow-hidden rounded-full">
            <div className="h-full rounded-full transition-all duration-500" style={{ width: `${(item.value / max) * 100}%`, backgroundColor: item.color.startsWith('color-mix') ? 'var(--main-blue)' : item.color }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

export function VerticalBarChart({ items }: { items: AnalyticsSegment[] }) {
  const max = Math.max(...items.map((i) => i.value), 1)
  const chartHeight = 160

  if (items.length === 0) return <p className="text-gray text-sm">Нет данных</p>

  return (
    <div className="flex gap-2 pt-1" style={{ height: chartHeight + 52 }}>
      {items.map((item) => {
        const barHeight = Math.max(6, Math.round((item.value / max) * chartHeight))
        return (
          <div key={item.id} className="flex min-w-0 flex-1 flex-col items-center gap-1.5">
            <span className="text-gray text-[10px] font-medium tabular-nums">{item.value}</span>
            <div className="flex w-full flex-1 items-end justify-center">
              <div className="w-full max-w-14 rounded-t-lg transition-all duration-500" style={{ height: barHeight, backgroundColor: item.color }} title={`${item.label}: ${item.value}`} />
            </div>
            <span className="text-gray line-clamp-2 w-full text-center text-[10px] leading-tight">{item.label}</span>
          </div>
        )
      })}
    </div>
  )
}

export function DonutChart({ items, size = 160 }: { items: AnalyticsSegment[]; size?: number }) {
  const total = items.reduce((s, i) => s + i.value, 0)
  if (total === 0) return <p className="text-gray text-sm">Нет данных</p>

  const radius = size / 2 - 12
  const cx = size / 2
  const cy = size / 2
  const sweeps = items.map((item) => (item.value / total) * 360)

  const arcs = items.map((item, index) => {
    const sweep = sweeps[index]
    const start = -90 + sweeps.slice(0, index).reduce((sum, value) => sum + value, 0)
    const end = start + sweep
    const large = sweep > 180 ? 1 : 0
    const startRad = (start * Math.PI) / 180
    const endRad = (end * Math.PI) / 180
    const x1 = cx + radius * Math.cos(startRad)
    const y1 = cy + radius * Math.sin(startRad)
    const x2 = cx + radius * Math.cos(endRad)
    const y2 = cy + radius * Math.sin(endRad)
    const d = sweep >= 359.9 ? `M ${cx - radius} ${cy} A ${radius} ${radius} 0 1 1 ${cx + radius} ${cy} A ${radius} ${radius} 0 1 1 ${cx - radius} ${cy}` : `M ${cx} ${cy} L ${x1} ${y1} A ${radius} ${radius} 0 ${large} 1 ${x2} ${y2} Z`
    return { ...item, d }
  })

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0">
        {arcs.map((arc) => (
          <path key={arc.id} d={arc.d} fill={arc.color.startsWith('color-mix') ? '#264b82' : arc.color} className="opacity-90" />
        ))}
        <circle cx={cx} cy={cy} r={radius * 0.55} fill="white" />
        <text x={cx} y={cy - 4} textAnchor="middle" className="fill-black text-lg font-bold" style={{ fontSize: 18 }}>
          {total}
        </text>
        <text x={cx} y={cy + 14} textAnchor="middle" className="fill-gray text-xs" style={{ fontSize: 11 }}>
          товаров
        </text>
      </svg>
      <ul className="min-w-0 flex-1 space-y-2">
        {items.map((item) => (
          <li key={item.id} className="flex items-center gap-2 text-sm">
            <span className="h-3 w-3 shrink-0 rounded-full" style={{ backgroundColor: item.color.startsWith('color-mix') ? '#264b82' : item.color }} />
            <span className="min-w-0 flex-1 truncate text-black">{item.label}</span>
            <span className="text-gray tabular-nums">
              {item.value} ({Math.round((item.value / total) * 100)}%)
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function SiteCompareChart({ rows }: { rows: { name: string; minPrice: number; maxPrice: number; medianPrice: number; color: string }[] }) {
  const globalMin = Math.min(...rows.map((r) => r.minPrice))
  const globalMax = Math.max(...rows.map((r) => r.maxPrice))
  const span = Math.max(globalMax - globalMin, 1)

  return (
    <ul className="space-y-4">
      {rows.map((row) => {
        const left = ((row.minPrice - globalMin) / span) * 100
        const width = ((row.maxPrice - row.minPrice) / span) * 100
        const medianLeft = ((row.medianPrice - globalMin) / span) * 100
        return (
          <li key={row.name}>
            <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-2 text-sm">
              <span className="font-medium text-black">{row.name}</span>
              <span className="text-gray text-xs tabular-nums">
                {formatPrice(row.minPrice)} – {formatPrice(row.maxPrice)} · мед. {formatPrice(row.medianPrice)}
              </span>
            </div>
            <div className="bg-pale-blue/50 relative h-3 rounded-full">
              <div className="absolute top-0 h-3 rounded-full opacity-90" style={{ left: `${left}%`, width: `${Math.max(width, 2)}%`, backgroundColor: row.color }} />
              <div className="border-main-blue absolute top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-white" style={{ left: `${medianLeft}%` }} title={`Медиана: ${formatPrice(row.medianPrice)}`} />
            </div>
          </li>
        )
      })}
    </ul>
  )
}

export function RatingBars({ items }: { items: { name: string; rating: number; productCount: number }[] }) {
  const maxRating = 5

  return (
    <ul className="space-y-3">
      {items.map((item) => (
        <li key={item.name}>
          <div className="mb-1 flex justify-between gap-2 text-sm">
            <span className="truncate font-medium">{item.name}</span>
            <span className="text-gray shrink-0 tabular-nums">
              {item.rating.toFixed(1)} · {item.productCount} тов.
            </span>
          </div>
          <div className="bg-pale-blue/60 h-2 overflow-hidden rounded-full">
            <div className="bg-orange h-full rounded-full" style={{ width: `${(item.rating / maxRating) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

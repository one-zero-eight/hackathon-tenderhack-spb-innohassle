import Input from '@/components/ui/Input'
import { cn } from '@/lib/cn'

type PriceRangeSliderProps = {
  min: number
  max: number
  valueMin: number
  valueMax: number
  onChange: (value: { min: number; max: number }) => void
  trackClassName?: string
  fillClassName?: string
  thumbClassName?: string
}

function clamp(value: number, low: number, high: number) {
  return Math.min(Math.max(value, low), high)
}

const rangeBaseClass =
  'pointer-events-none absolute top-0 left-0 h-8 w-full appearance-none bg-transparent [&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:bg-white [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:bg-white'

export default function PriceRangeSlider({
  min,
  max,
  valueMin,
  valueMax,
  onChange,
  trackClassName = 'bg-pale-blue',
  fillClassName = 'bg-main-blue',
  thumbClassName = '[&::-moz-range-thumb]:border-main-blue [&::-webkit-slider-thumb]:border-main-blue',
}: PriceRangeSliderProps) {
  const range = Math.max(max - min, 1)
  const left = ((valueMin - min) / range) * 100
  const right = 100 - ((valueMax - min) / range) * 100

  const setMin = (value: number) => onChange({ min: Math.min(clamp(value, min, max), valueMax), max: valueMax })
  const setMax = (value: number) => onChange({ min: valueMin, max: Math.max(clamp(value, min, max), valueMin) })

  const parseInput = (raw: string) => {
    const digits = raw.replace(/\s/g, '')
    if (!digits) return null
    const value = Number(digits)
    return Number.isFinite(value) ? value : null
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <Input
          size="sm"
          inputMode="numeric"
          placeholder="От"
          value={String(valueMin)}
          onChange={(e) => {
            const value = parseInput(e.target.value)
            if (value != null) setMin(value)
          }}
        />
        <Input
          size="sm"
          inputMode="numeric"
          placeholder="До"
          value={String(valueMax)}
          onChange={(e) => {
            const value = parseInput(e.target.value)
            if (value != null) setMax(value)
          }}
        />
      </div>

      <div className="relative h-8">
        <div className={cn('absolute top-1/2 right-0 left-0 h-1 -translate-y-1/2 rounded-full', trackClassName)} />
        <div className={cn('absolute top-1/2 h-1 -translate-y-1/2 rounded-full', fillClassName)} style={{ left: `${left}%`, right: `${right}%` }} />

        <input type="range" min={min} max={max} step={100} value={valueMin} onChange={(e) => setMin(Number(e.target.value))} className={cn(rangeBaseClass, thumbClassName)} aria-label="Минимальная цена" />
        <input type="range" min={min} max={max} step={100} value={valueMax} onChange={(e) => setMax(Number(e.target.value))} className={cn(rangeBaseClass, thumbClassName)} aria-label="Максимальная цена" />
      </div>
    </div>
  )
}

import Input from '@/components/ui/Input'
import { cn } from '@/lib/cn'
import { buildPricePresets, isPricePresetActive } from '@/lib/pricePresets'
import { useEffect, useMemo, useState } from 'react'

type PriceRangeSliderProps = {
  min: number
  max: number
  valueMin: number
  valueMax: number
  onChange: (value: { min: number; max: number }) => void
  trackClassName?: string
  fillClassName?: string
  thumbClassName?: string
  presetRadioRingSelectedClassName?: string
  presetRadioDotSelectedClassName?: string
}

type ActiveThumb = 'min' | 'max' | null

function clamp(value: number, low: number, high: number) {
  return Math.min(Math.max(value, low), high)
}

function getPriceStep(low: number, high: number) {
  const span = high - low
  if (span <= 2_000) return 1
  if (span <= 20_000) return 10
  if (span <= 200_000) return 100
  return 1_000
}

const rangeBaseClass =
  'pointer-events-none absolute top-0 left-0 h-8 w-full appearance-none bg-transparent [&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:relative [&::-moz-range-thumb]:z-10 [&::-moz-range-thumb]:h-4 [&::-moz-range-thumb]:w-4 [&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:bg-white [&::-moz-range-track]:pointer-events-none [&::-webkit-slider-runnable-track]:pointer-events-none [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:relative [&::-webkit-slider-thumb]:z-10 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:bg-white'

export default function PriceRangeSlider({
  min,
  max,
  valueMin,
  valueMax,
  onChange,
  trackClassName = 'bg-pale-blue',
  fillClassName = 'bg-main-blue',
  thumbClassName = '[&::-moz-range-thumb]:border-main-blue [&::-webkit-slider-thumb]:border-main-blue',
  presetRadioRingSelectedClassName = 'border-main-blue',
  presetRadioDotSelectedClassName = 'bg-main-blue',
}: PriceRangeSliderProps) {
  const [activeThumb, setActiveThumb] = useState<ActiveThumb>(null)
  const range = Math.max(max - min, 1)
  const step = getPriceStep(min, max)
  const pricePresets = useMemo(() => buildPricePresets(min, max), [min, max])
  const left = ((valueMin - min) / range) * 100
  const right = 100 - ((valueMax - min) / range) * 100
  const thumbsOverlap = valueMax - valueMin <= step

  const { minZIndex, maxZIndex } = useMemo(() => {
    if (activeThumb === 'min') return { minZIndex: 5, maxZIndex: 2 }
    if (activeThumb === 'max') return { minZIndex: 2, maxZIndex: 5 }

    if (thumbsOverlap) {
      const sliderMid = min + range / 2
      if (valueMin >= sliderMid) return { minZIndex: 5, maxZIndex: 3 }
      return { minZIndex: 3, maxZIndex: 5 }
    }

    return { minZIndex: 3, maxZIndex: 4 }
  }, [activeThumb, min, range, thumbsOverlap, valueMin])

  useEffect(() => {
    const clearActive = () => setActiveThumb(null)
    window.addEventListener('pointerup', clearActive)
    window.addEventListener('pointercancel', clearActive)
    return () => {
      window.removeEventListener('pointerup', clearActive)
      window.removeEventListener('pointercancel', clearActive)
    }
  }, [])

  const setMin = (value: number) => onChange({ min: Math.min(clamp(value, min, max), valueMax), max: valueMax })
  const setMax = (value: number) => onChange({ min: valueMin, max: Math.max(clamp(value, min, max), valueMin) })

  const parseInput = (raw: string) => {
    const digits = raw.replace(/\s/g, '')
    if (!digits) return null
    const value = Number(digits)
    return Number.isFinite(value) ? value : null
  }

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-3">
        <Input
          size="md"
          className="rounded-lg"
          inputMode="numeric"
          placeholder="От"
          value={String(valueMin)}
          onChange={(e) => {
            const value = parseInput(e.target.value)
            if (value != null) setMin(value)
          }}
        />
        <Input
          size="md"
          className="rounded-lg"
          inputMode="numeric"
          placeholder="До"
          value={String(valueMax)}
          onChange={(e) => {
            const value = parseInput(e.target.value)
            if (value != null) setMax(value)
          }}
        />
      </div>

      {pricePresets.length > 0 && (
        <ul className="space-y-0.5" role="radiogroup" aria-label="Ценовые диапазоны">
          {pricePresets.map((preset) => {
            const selected = isPricePresetActive(preset, valueMin, valueMax)

            return (
              <li key={preset.id}>
                <button
                  type="button"
                  role="radio"
                  aria-checked={selected}
                  onClick={() => onChange({ min: preset.min, max: preset.max })}
                  className="hover:bg-pale-blue/50 flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-1 py-1.5 text-left text-sm text-black transition-colors"
                >
                  <span
                    className={cn(
                      'flex h-4 w-4 shrink-0 items-center justify-center rounded-full border-2 transition-colors',
                      selected ? presetRadioRingSelectedClassName : 'border-gray-blue',
                    )}
                    aria-hidden
                  >
                    {selected && <span className={cn('h-2 w-2 rounded-full', presetRadioDotSelectedClassName)} />}
                  </span>
                  <span className="min-w-0 flex-1 truncate">{preset.label}</span>
                </button>
              </li>
            )
          })}
        </ul>
      )}

      <div className="relative h-8">
        <div className={cn('absolute top-1/2 right-0 left-0 h-1 -translate-y-1/2 rounded-full', trackClassName)} />
        <div className={cn('absolute top-1/2 h-1 -translate-y-1/2 rounded-full', fillClassName)} style={{ left: `${left}%`, right: `${right}%` }} />

        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={valueMin}
          onPointerDown={() => setActiveThumb('min')}
          onChange={(e) => setMin(Number(e.target.value))}
          className={cn(rangeBaseClass, thumbClassName)}
          style={{ zIndex: minZIndex }}
          aria-label="Минимальная цена"
        />
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={valueMax}
          onPointerDown={() => setActiveThumb('max')}
          onChange={(e) => setMax(Number(e.target.value))}
          className={cn(rangeBaseClass, thumbClassName)}
          style={{ zIndex: maxZIndex }}
          aria-label="Максимальная цена"
        />
      </div>
    </div>
  )
}

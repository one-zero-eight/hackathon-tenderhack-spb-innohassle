export type PricePreset = {
  id: string
  label: string
  min: number
  max: number
}

const PRESET_TEMPLATES = [
  { id: 'to-1k', label: 'до 1 000', min: Number.NEGATIVE_INFINITY, max: 1_000 },
  { id: '1k-5k', label: '1–5 тыс.', min: 1_000, max: 5_000 },
  { id: '5k-20k', label: '5–20 тыс.', min: 5_000, max: 20_000 },
  { id: '20k-plus', label: '20 тыс.+', min: 20_000, max: Number.POSITIVE_INFINITY },
] as const

/** Presets clamped to the current product price span; skips empty buckets. */
export function buildPricePresets(catalogMin: number, catalogMax: number): PricePreset[] {
  if (catalogMax <= catalogMin) return []

  return PRESET_TEMPLATES.map((template) => ({
    id: template.id,
    label: template.label,
    min: Math.max(template.min === Number.NEGATIVE_INFINITY ? catalogMin : template.min, catalogMin),
    max: Math.min(template.max === Number.POSITIVE_INFINITY ? catalogMax : template.max, catalogMax),
  })).filter((preset) => preset.max > preset.min)
}

export function isPricePresetActive(preset: PricePreset, valueMin: number, valueMax: number) {
  return preset.min === valueMin && preset.max === valueMax
}

import { createContext } from 'react'
import type { CityOption } from '@/lib/geo'

export type CityContextValue = {
  city: CityOption
  setCity: (city: CityOption) => void
}

export const CityContext = createContext<CityContextValue | null>(null)

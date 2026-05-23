import { CityContext } from '@/context/city-context'
import { detectCity, getDefaultCity, getPopularCities, type CityOption } from '@/lib/geo'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

const STORAGE_KEY = 'selected-city-label'

function readStoredCity(): CityOption | null {
  try {
    const label = localStorage.getItem(STORAGE_KEY)
    if (!label) return null
    return getPopularCities().find((city) => city.label === label) ?? { id: 0, value: label, label }
  } catch {
    return null
  }
}

function sameCity(a: CityOption, b: CityOption): boolean {
  return a.label === b.label && a.value === b.value && a.id === b.id
}

export function CityProvider({ children }: { children: ReactNode }) {
  const [city, setCityState] = useState<CityOption>(() => readStoredCity() ?? getDefaultCity())

  useEffect(() => {
    let cancelled = false
    detectCity().then((found) => {
      if (!cancelled && found && !localStorage.getItem(STORAGE_KEY)) {
        setCityState((prev) => (sameCity(prev, found) ? prev : found))
      }
    })
    return () => {
      cancelled = true
    }
  }, [])

  const setCity = useCallback((next: CityOption) => {
    setCityState((prev) => {
      if (sameCity(prev, next)) return prev
      try {
        localStorage.setItem(STORAGE_KEY, next.label)
      } catch {
        /* ignore */
      }
      return next
    })
  }, [])

  const value = useMemo(() => ({ city, setCity }), [city, setCity])

  return <CityContext.Provider value={value}>{children}</CityContext.Provider>
}

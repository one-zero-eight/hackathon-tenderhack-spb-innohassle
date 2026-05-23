import { CityContext } from '@/context/city-context'
import { detectCity, getCityLocation, getDefaultCity, getPopularCities, NO_CITY_OPTION, type CityOption } from '@/lib/geo'
import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react'

const STORAGE_KEY = 'selected-city-label'

function readStoredCity(): CityOption | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === null) return null
    if (stored === '') return NO_CITY_OPTION
    return getPopularCities().find((city) => city.label === stored) ?? { id: 0, value: stored, label: stored }
  } catch {
    return null
  }
}

function sameCity(a: CityOption, b: CityOption): boolean {
  return a.label === b.label && a.value === b.value && a.id === b.id
}

export function CityProvider({ children }: { children: ReactNode }) {
  const [city, setCityState] = useState<CityOption>(() => readStoredCity() ?? getDefaultCity())
  const detectionStarted = useRef(false)

  const runCityDetection = useCallback(() => {
    if (detectionStarted.current) return
    if (typeof window === 'undefined') return
    if (localStorage.getItem(STORAGE_KEY) !== null) return

    detectionStarted.current = true
    let cancelled = false

    detectCity().then((found) => {
      if (!cancelled && found) {
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
        localStorage.setItem(STORAGE_KEY, getCityLocation(next))
      } catch {
        /* ignore */
      }
      return next
    })
  }, [])

  const value = useMemo(() => ({ city, setCity, runCityDetection }), [city, setCity, runCityDetection])

  return <CityContext.Provider value={value}>{children}</CityContext.Provider>
}

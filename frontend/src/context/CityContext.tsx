import { CityContext } from '@/context/city-context'
import { detectCity, getDefaultCity, getPopularCities, type CityOption } from '@/lib/geo'
import { useEffect, useState, type ReactNode } from 'react'

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

export function CityProvider({ children }: { children: ReactNode }) {
  const [city, setCityState] = useState<CityOption>(() => readStoredCity() ?? getDefaultCity())

  useEffect(() => {
    let cancelled = false
    detectCity().then((found) => {
      if (!cancelled && found && !localStorage.getItem(STORAGE_KEY)) {
        setCityState(found)
      }
    })
    return () => {
      cancelled = true
    }
  }, [])

  const setCity = (next: CityOption) => {
    setCityState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next.label)
    } catch {
      /* ignore */
    }
  }

  return <CityContext.Provider value={{ city, setCity }}>{children}</CityContext.Provider>
}

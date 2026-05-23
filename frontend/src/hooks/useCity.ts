import { CityContext } from '@/context/city-context'
import { useContext, useEffect } from 'react'

export function useCity() {
  const ctx = useContext(CityContext)
  if (!ctx) throw new Error('useCity must be used within CityProvider')

  useEffect(() => {
    return ctx.runCityDetection()
  }, [ctx.runCityDetection])

  return ctx
}

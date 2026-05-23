import { useEffect, useState } from 'react'

const BREAKPOINTS = [
  { query: '(min-width: 1024px)', count: 5 },
  { query: '(min-width: 768px)', count: 4 },
  { query: '(min-width: 640px)', count: 3 },
] as const

export function getVisibleProductCount() {
  if (typeof window === 'undefined') return 2
  for (const { query, count } of BREAKPOINTS) {
    if (window.matchMedia(query).matches) return count
  }
  return 2
}

export function useVisibleProductCount() {
  const [count, setCount] = useState(getVisibleProductCount)

  useEffect(() => {
    const update = () => setCount(getVisibleProductCount())
    update()

    const listeners = BREAKPOINTS.map(({ query }) => {
      const mql = window.matchMedia(query)
      mql.addEventListener('change', update)
      return mql
    })

    return () => {
      for (const mql of listeners) mql.removeEventListener('change', update)
    }
  }, [])

  return count
}

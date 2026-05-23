import { useVisibleProductCount } from '@/lib/useVisibleProductCount'

export function ResultsSkeleton() {
  const visibleCount = useVisibleProductCount()
  const cardCount = visibleCount + 1

  return (
    <div className="space-y-6">
      {[0, 1].map((section) => (
        <div key={section} className="border-gray-blue/60 animate-pulse rounded-3xl border bg-white p-4">
          <div className="bg-pale-blue mb-4 h-6 w-40 rounded" />
          <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${cardCount}, minmax(0, 1fr))` }}>
            {Array.from({ length: cardCount }, (_, card) => (
              <div key={card} className="min-w-0 rounded-2xl bg-white p-2">
                <div className="bg-pale-blue aspect-3/4 rounded-xl" />
                <div className="space-y-2 px-0.5 pt-2">
                  <div className="bg-pale-blue h-4 w-16 rounded" />
                  <div className="bg-pale-blue h-3 rounded" />
                  <div className="bg-pale-blue h-3 w-4/5 rounded" />
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

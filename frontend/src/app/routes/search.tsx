import { createFileRoute, Link, useNavigate } from '@tanstack/react-router'
import CitySelect from '@/components/shared/CitySelect'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import { useCity } from '@/hooks/useCity'
import { useYandexSuggest } from '@/hooks/useYandexSuggest'
import { cn } from '@/lib/cn'
import { getCityLocation } from '@/lib/geo'
import { pickRandomSearchExamples, pickRandomSearchPlaceholder } from '@/lib/searchExamples'
import { useRef, useState } from 'react'
import { IoClose, IoSearch, IoTimeOutline } from 'react-icons/io5'

export const Route = createFileRoute('/search')({
  component: SearchPage,
})

function SearchPage() {
  const [quickSearches] = useState(pickRandomSearchExamples)
  const [placeholderExample] = useState(pickRandomSearchPlaceholder)
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [suggestOpen, setSuggestOpen] = useState(false)
  const navigate = useNavigate()
  const { city } = useCity()
  const searchRef = useRef<HTMLDivElement>(null)
  const { items: suggestions, loading: suggestLoading } = useYandexSuggest(query)

  const submitQuery = (value: string) => {
    const trimmed = value.trim()
    if (!trimmed || searching) return
    setSuggestOpen(false)
    setSearching(true)
    void navigate({ to: '/sites', search: { q: trimmed, location: getCityLocation(city) } })
  }

  const onSearch = (e: React.FormEvent) => {
    e.preventDefault()
    submitQuery(query)
  }

  const showSuggestions = suggestOpen && query.trim().length > 0 && (suggestLoading || suggestions.length > 0)

  const pickSuggestion = (text: string) => {
    setQuery(text)
    submitQuery(text)
  }

  return (
    <div className="from-pale-blue relative min-h-screen overflow-hidden via-white to-white">
      <div aria-hidden className="bg-main-blue/10 pointer-events-none absolute -top-24 left-1/2 h-72 w-xl -translate-x-1/2 rounded-full blur-3xl" />
      <div aria-hidden className="bg-orange/10 pointer-events-none absolute top-40 -right-20 h-56 w-56 rounded-full blur-3xl" />

      <div className="absolute top-4 right-4 z-10 sm:top-6 sm:right-6">
        <CitySelect className="rounded-xl bg-white/80 backdrop-blur-sm" />
      </div>

      <main className="relative flex min-h-screen flex-col items-center justify-start px-4 pt-[18vh] pb-24 sm:pt-[22vh]">
        <div className="w-full max-w-3xl">
          <h1 className="mb-10 text-center text-4xl font-bold tracking-tight text-black sm:text-3xl">Найдите лучшую цену на маркетплейсах</h1>
          <div ref={searchRef} className={cn('relative z-50 w-full', showSuggestions ? 'border-gray-blue/60 overflow-hidden rounded-2xl border bg-white' : 'rounded-full')}>
            <form onSubmit={onSearch} className={cn('flex w-full items-stretch', showSuggestions ? 'border-gray-blue/60 border-b' : undefined)}>
              <Input
                size="lg"
                variant={showSuggestions ? 'outline' : 'fill'}
                placeholder={`Что ищете? Например, ${placeholderExample}`}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onFocus={() => setSuggestOpen(true)}
                onBlur={() => window.setTimeout(() => setSuggestOpen(false), 150)}
                leadingIcon={<IoSearch size={22} />}
                className={cn('h-full min-w-0 flex-1 border-r-0', showSuggestions ? 'rounded-none border-0! bg-transparent px-4 py-3.5 text-black' : 'rounded-l-full bg-white')}
                autoComplete="off"
              />
              {query && (
                <button type="button" onClick={() => setQuery('')} aria-label="Очистить" className={cn('text-gray flex shrink-0 cursor-pointer items-center justify-center hover:text-black', showSuggestions ? 'px-2' : 'bg-white px-3')}>
                  <IoClose size={22} />
                </button>
              )}
              <Button type="submit" variant="primary" size={showSuggestions ? 'sm' : 'lg'} disabled={searching} className={cn('shrink-0', showSuggestions ? 'my-2.5 mr-2.5 self-center rounded-xl px-5' : 'h-full! rounded-r-full px-8 pr-9')}>
                {searching ? <LoadingSpinner size="md" className="text-white" /> : 'Поиск'}
              </Button>
            </form>

            {showSuggestions && (
              <ul className="py-1.5">
                {suggestLoading && suggestions.length === 0 && (
                  <li className="text-gray flex items-center gap-3 px-4 py-3 text-sm">
                    <IoTimeOutline className="shrink-0" size={18} />
                    Загрузка…
                  </li>
                )}
                {suggestions.map((text) => (
                  <li key={text}>
                    <button
                      type="button"
                      className="hover:bg-pale-blue/60 mx-1.5 flex w-[calc(100%-0.75rem)] cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => pickSuggestion(text)}
                    >
                      <IoSearch className="text-gray shrink-0" size={18} />
                      <span className="truncate text-sm text-black">{text}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="mt-6 flex flex-col items-center gap-3">
            <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2">
              {quickSearches.map((item) => (
                <Link key={item} to="/sites" search={{ q: item, location: getCityLocation(city) }} className="text-main-blue text-sm underline underline-offset-2 hover:opacity-80">
                  {item}
                </Link>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

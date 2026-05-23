import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import CitySelect from '@/components/shared/CitySelect'
import { useYandexSuggest } from '@/hooks/useYandexSuggest'
import { cn } from '@/lib/cn'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useRef, useState } from 'react'
import { IoClose, IoSearch, IoTimeOutline } from 'react-icons/io5'

export const Route = createFileRoute('/')({
  component: HomePage,
})

function HomePage() {
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [suggestOpen, setSuggestOpen] = useState(false)
  const navigate = useNavigate()
  const searchRef = useRef<HTMLDivElement>(null)
  const { items: suggestions, loading: suggestLoading } = useYandexSuggest(query)

  const submitQuery = (value: string) => {
    const trimmed = value.trim()
    if (!trimmed || searching) return
    setSuggestOpen(false)
    setSearching(true)
    void navigate({ to: '/sites', search: { q: trimmed } })
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
    <div className="relative flex min-h-full flex-1 flex-col">
      <div className="absolute top-4 right-4 flex gap-2 sm:top-6 sm:right-6">
        <CitySelect className="w-44 sm:w-52" />
      </div>

      <main className="flex flex-1 flex-col items-center justify-start gap-15 px-4 pt-[28vh] pb-24 sm:pt-[32vh]">
        <div className="flex flex-col items-center justify-center gap-2">
          <h2 className="text-3xl font-bold">Поиск товаров на сайтах</h2>
          <p className="text-gray-500">Найдите товары на сайте по названию, артикулу или описанию</p>
        </div>

        <div ref={searchRef} className={cn('relative z-50 w-full max-w-4xl', showSuggestions ? 'border-gray-blue overflow-hidden rounded-2xl border bg-white shadow-lg' : undefined)}>
          <form onSubmit={onSearch} className={cn('flex w-full items-stretch', showSuggestions ? 'border-gray-blue border-b' : undefined)}>
            <Input
              size="lg"
              variant={showSuggestions ? 'outline' : 'fill'}
              placeholder="Искать на сайте"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => setSuggestOpen(true)}
              onBlur={() => window.setTimeout(() => setSuggestOpen(false), 150)}
              leadingIcon={<IoSearch size={22} />}
              className={cn('h-full min-w-0 flex-1 border-r-0', showSuggestions ? 'rounded-none border-0! bg-transparent px-4 py-3.5' : 'rounded-l-full')}
              autoComplete="off"
            />
            {query && (
              <button type="button" onClick={() => setQuery('')} aria-label="Очистить" className={cn('text-gray flex shrink-0 cursor-pointer items-center justify-center hover:text-gray-600', showSuggestions ? 'px-2' : 'bg-pale-blue px-3')}>
                <IoClose size={22} />
              </button>
            )}
            <Button type="submit" variant="primary" size={showSuggestions ? 'sm' : 'lg'} disabled={searching} className={cn('shrink-0', showSuggestions ? 'my-2.5 mr-2.5 self-center rounded-lg px-4' : 'h-full! rounded-r-full px-8 pr-9')}>
              {searching ? <LoadingSpinner size="md" className="text-white" /> : 'Поиск'}
            </Button>
          </form>

          {showSuggestions && (
            <ul className="py-1">
              {suggestLoading && suggestions.length === 0 && (
                <li className="text-gray flex items-center gap-3 px-4 py-3 text-sm">
                  <IoTimeOutline className="shrink-0" size={18} />
                  Загрузка…
                </li>
              )}
              {suggestions.map((text) => (
                <li key={text}>
                  <button type="button" className="hover:bg-pale-blue/50 flex w-full cursor-pointer items-center gap-3 px-4 py-3 text-left" onMouseDown={(e) => e.preventDefault()} onClick={() => pickSuggestion(text)}>
                    <IoSearch className="text-gray shrink-0" size={18} />
                    <span className="truncate text-sm text-black">{text}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </main>
    </div>
  )
}

import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import LoadingSpinner from '@/components/ui/LoadingSpinner'
import CitySelect from '@/components/shared/CitySelect'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { IoClose, IoSearch } from 'react-icons/io5'

export const Route = createFileRoute('/')({
  component: HomePage,
})

function HomePage() {
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const navigate = useNavigate()

  const onSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim() || searching) return
    setSearching(true)
    void navigate({ to: '/sites', search: { q: query.trim() } })
  }

  return (
    <div className="relative flex min-h-full flex-1 flex-col">
      <div className="absolute top-4 right-4 flex gap-2 sm:top-6 sm:right-6">
        <CitySelect className="w-44 sm:w-52" />
      </div>

      <main className="flex flex-1 flex-col items-center justify-center gap-15 px-4 pb-24">
        <div className="flex flex-col items-center justify-center gap-2">
          <h2 className="text-3xl font-bold">Поиск товаров на сайтах</h2>
          <p className="text-gray-500">Найдите товары на сайте по названию, артикулу или описанию</p>
        </div>
        <form onSubmit={onSearch} className="flex w-full max-w-4xl items-stretch">
          <Input size="lg" variant="fill" placeholder="Искать на сайте" value={query} onChange={(e) => setQuery(e.target.value)} leadingIcon={<IoSearch size={22} />} className="h-full min-w-0 flex-1 rounded-l-full border-r-0" />
          {query && (
            <button type="button" onClick={() => setQuery('')} aria-label="Очистить" className="bg-pale-blue text-gray flex shrink-0 cursor-pointer items-center justify-center px-3 hover:text-gray-600">
              <IoClose size={22} />
            </button>
          )}
          <Button type="submit" variant="primary" size="lg" disabled={searching} className="h-full! shrink-0 rounded-r-full px-8 pr-9">
            {searching ? <LoadingSpinner size="md" className="text-white" /> : 'Поиск'}
          </Button>
        </form>
      </main>
    </div>
  )
}

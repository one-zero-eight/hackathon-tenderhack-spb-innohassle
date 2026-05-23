import Dropdown from '@/components/ui/Dropdown'
import { detectCity, filterCities, getDefaultCity, getPopularCities, mergeCityOptions, searchCities, type CityOption } from '@/lib/geo'
import { useEffect, useMemo, useState } from 'react'
import { IoLocationSharp } from 'react-icons/io5'

type Props = {
  className?: string
}

export default function CitySelect({ className }: Props) {
  const popularCities = useMemo(() => getPopularCities(), [])
  const defaultCity = useMemo(() => getDefaultCity(), [])
  const [city, setCity] = useState<CityOption>(defaultCity)
  const [options, setOptions] = useState<CityOption[]>(popularCities)
  const [search, setSearch] = useState('')

  useEffect(() => {
    let cancelled = false
    detectCity().then((found) => {
      if (!cancelled && found) setCity(found)
    })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    const q = search.trim()
    if (!q) {
      setOptions(popularCities)
      return
    }

    const local = filterCities(popularCities, q)
    if (q.length < 2) {
      setOptions(local)
      return
    }

    const timer = setTimeout(() => {
      searchCities(q).then((remote) => {
        setOptions(mergeCityOptions(local, remote))
      })
    }, 150)

    return () => clearTimeout(timer)
  }, [search, popularCities])

  return (
    <Dropdown
      className={className}
      variant="ghost"
      options={options}
      value={city.value}
      displayLabel={city.label}
      placeholder="Город"
      searchable
      searchSize="md"
      searchPlaceholder="Поиск города"
      menuClassName="min-w-80 w-80"
      searchValue={search}
      onSearchChange={setSearch}
      emptyMessage="Ничего не найдено"
      trailingIcon={<IoLocationSharp size={18} />}
      onSelect={(value) => {
        const picked = [...options, ...popularCities].find((o) => o.value === value)
        if (picked) {
          setCity(picked)
          setSearch('')
          setOptions(popularCities)
        }
      }}
    />
  )
}

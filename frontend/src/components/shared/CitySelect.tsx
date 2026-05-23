import Dropdown from '@/components/ui/Dropdown'
import { useCity } from '@/hooks/useCity'
import { filterCities, getPopularCities, mergeCityOptions, searchCities, type CityOption } from '@/lib/geo'
import { useEffect, useMemo, useState } from 'react'
import { IoLocationSharp, IoSearch } from 'react-icons/io5'

type Props = {
  className?: string
  onCityChange?: (city: CityOption) => void
}

function CityMenuHeader({ remoteQuery }: { remoteQuery: string }) {
  if (remoteQuery) {
    return <p className="text-gray px-4 pt-2.5 pb-0.5 text-[11px] font-medium tracking-wide uppercase">Результаты поиска</p>
  }

  return <p className="text-gray px-4 pt-2.5 pb-0.5 text-[11px] font-medium tracking-wide uppercase">Совпадения</p>
}

export default function CitySelect({ className, onCityChange }: Props) {
  const { city, setCity } = useCity()
  const popularCities = useMemo(() => getPopularCities(), [])
  const [search, setSearch] = useState('')
  const [remoteOptions, setRemoteOptions] = useState<CityOption[]>([])
  const remoteQuery = search.trim().length >= 2 ? search.trim() : ''

  const localOptions = useMemo(() => {
    const q = search.trim()
    if (!q) return popularCities
    return filterCities(popularCities, q)
  }, [search, popularCities])

  useEffect(() => {
    if (!remoteQuery) return

    let cancelled = false
    const timer = setTimeout(() => {
      searchCities(remoteQuery).then((remote) => {
        if (!cancelled) setRemoteOptions(remote)
      })
    }, 150)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [remoteQuery])

  const options = useMemo(() => (remoteQuery ? mergeCityOptions(localOptions, remoteOptions) : localOptions), [localOptions, remoteOptions, remoteQuery])

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
      menuClassName="w-80 min-w-80"
      menuHeader={<CityMenuHeader remoteQuery={remoteQuery} />}
      searchLeadingIcon={<IoSearch size={16} />}
      searchValue={search}
      onSearchChange={setSearch}
      emptyMessage="Ничего не найдено"
      trailingIcon={<IoLocationSharp size={18} />}
      onSelect={(value) => {
        const picked = [...options, ...popularCities, city].find((o) => o.value === value)
        if (picked) {
          setCity(picked)
          onCityChange?.(picked)
          setSearch('')
        }
      }}
    />
  )
}

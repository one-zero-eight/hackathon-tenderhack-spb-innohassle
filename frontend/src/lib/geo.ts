const PHOTON = 'https://photon.komoot.io'

type PhotonProperties = {
  osm_id: number
  name?: string
  city?: string
  state?: string
  countrycode?: string
  type?: string
  osm_key?: string
  osm_value?: string
}

type PhotonFeature = {
  properties: PhotonProperties
}

export type CityOption = {
  id: number
  value: string
  label: string
}

const POPULAR_CITY_NAMES = [
  'Москва',
  'Санкт-Петербург',
  'Новосибирск',
  'Екатеринбург',
  'Казань',
  'Нижний Новгород',
  'Челябинск',
  'Самара',
  'Омск',
  'Ростов-на-Дону',
  'Уфа',
  'Красноярск',
  'Иннополис',
  'Пермь',
  'Волгоград',
  'Краснодар',
  'Саратов',
  'Тюмень',
  'Тольятти',
  'Ижевск',
  'Барнаул',
  'Иркутск',
  'Хабаровск',
  'Ярославль',
  'Владивосток',
  'Махачкала',
  'Томск',
  'Ульяновск',
  'Кемерово',
  'Рязань',
  'Киров',
]

function toCityOption(label: string, id: number): CityOption {
  const trimmed = label.trim()
  return { id, value: String(id), label: trimmed }
}

export function getDefaultCity(): CityOption {
  return getPopularCities().find((city) => city.label === 'Санкт-Петербург') ?? toCityOption('Санкт-Петербург', 2)
}

export const NO_CITY_OPTION: CityOption = { id: -1, value: '', label: 'Не указано' }

export function getCityLocation(city: CityOption): string {
  return city.value === '' ? '' : city.label
}

export function getPopularCities(): CityOption[] {
  return POPULAR_CITY_NAMES.map((name, index) => toCityOption(name, index + 1))
}

function mergeCityOptions(...lists: CityOption[][]): CityOption[] {
  const seen = new Set<string>()
  const merged: CityOption[] = []
  for (const list of lists) {
    for (const item of list) {
      const key = item.label.trim().toLowerCase()
      if (seen.has(key)) continue
      seen.add(key)
      merged.push(item)
    }
  }
  return merged
}

function isRuCityFeature(feature: PhotonFeature): boolean {
  const p = feature.properties
  if (p.countrycode !== 'RU') return false
  return p.type === 'city' || p.type === 'town' || p.type === 'state' || p.type === 'administrative' || Boolean(p.city)
}

function isRuCitySearchFeature(feature: PhotonFeature): boolean {
  const p = feature.properties
  if (p.countrycode !== 'RU') return false
  if (p.osm_key === 'place' && (p.osm_value === 'city' || p.osm_value === 'town' || p.osm_value === 'village')) {
    return true
  }
  return p.type === 'city' || p.type === 'town' || p.type === 'state'
}

function featureToCity(feature: PhotonFeature): CityOption | null {
  const p = feature.properties
  const label = p.name ?? p.city ?? p.state
  if (!label || label.trim().length < 2) return null
  return toCityOption(label, p.osm_id)
}

function photonFeaturesToCityOptions(features: PhotonFeature[], match: (feature: PhotonFeature) => boolean): CityOption[] {
  const seen = new Set<string>()
  const options: CityOption[] = []

  for (const feature of features) {
    if (!match(feature)) continue
    const city = featureToCity(feature)
    if (!city) continue
    const key = city.label.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    options.push(city)
  }

  return options
}

async function photonFetch(path: string, params: Record<string, string>) {
  const url = new URL(path, PHOTON)
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v)
  const res = await fetch(url, { signal: AbortSignal.timeout(5000) })
  if (!res.ok) throw new Error(`Geocoding failed: ${res.status}`)
  return res.json()
}

async function reverseGeocode(lat: number, lon: number): Promise<CityOption | null> {
  const data = (await photonFetch('/reverse', { lat: String(lat), lon: String(lon) })) as { features: PhotonFeature[] }
  for (const feature of data.features ?? []) {
    if (!isRuCityFeature(feature)) continue
    const city = featureToCity(feature)
    if (city) return city
  }
  return null
}

export function filterCities(cities: CityOption[], query: string): CityOption[] {
  const q = query.trim().toLowerCase()
  if (!q) return cities
  return cities.filter((city) => city.label.toLowerCase().includes(q))
}

export async function searchCities(query: string): Promise<CityOption[]> {
  const q = query.trim()
  if (q.length < 2) return []

  const data = (await photonFetch('/api', { q, limit: '20' })) as { features: PhotonFeature[] }
  return photonFeaturesToCityOptions(data.features ?? [], isRuCitySearchFeature)
}

async function detectCityByIp(): Promise<CityOption | null> {
  try {
    const res = await fetch('https://geo.kamero.ai/api/geo', { signal: AbortSignal.timeout(4000) })
    if (!res.ok) return null

    const data = (await res.json()) as {
      country?: string
      city?: string
      latitude?: string | number
      longitude?: string | number
    }

    if (data.country !== 'RU') return null

    const latitude = data.latitude != null ? Number(data.latitude) : null
    const longitude = data.longitude != null ? Number(data.longitude) : null

    if (latitude != null && longitude != null && Number.isFinite(latitude) && Number.isFinite(longitude)) {
      const city = await reverseGeocode(latitude, longitude)
      if (city) return city
    }

    if (data.city) {
      const match = getPopularCities().find((c) => c.label.toLowerCase() === data.city!.toLowerCase())
      if (match) return match
      const found = await searchCities(data.city)
      return found[0] ?? null
    }
  } catch {
    return null
  }

  return null
}

export async function detectCity(): Promise<CityOption | null> {
  const ipTask = detectCityByIp()

  if (typeof navigator !== 'undefined' && navigator.geolocation) {
    const geoTask = new Promise<CityOption | null>((resolve) => {
      navigator.geolocation.getCurrentPosition(
        async (pos) => resolve(await reverseGeocode(pos.coords.latitude, pos.coords.longitude)),
        () => resolve(null),
        { timeout: 5000, maximumAge: 600_000 },
      )
    })

    const [geo, ip] = await Promise.all([geoTask, ipTask])
    return geo ?? ip
  }

  return ipTask
}

export { mergeCityOptions }

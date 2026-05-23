const PHOTON = 'https://photon.komoot.io'
const NOMINATIM = 'https://nominatim.openstreetmap.org'
const USER_AGENT = 'TenderHack/1.0'

type PhotonProperties = {
  osm_id: number
  name?: string
  city?: string
  state?: string
  countrycode?: string
  type?: string
}

type PhotonFeature = {
  properties: PhotonProperties
}

type NominatimAddress = {
  city?: string
  town?: string
  village?: string
  municipality?: string
  state?: string
  country_code?: string
}

type NominatimResult = {
  place_id: number
  name?: string
  display_name: string
  type?: string
  class?: string
  place_rank?: number
  addresstype?: string
  address?: NominatimAddress
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
  'Воронеж',
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

function featureToCity(feature: PhotonFeature): CityOption | null {
  const p = feature.properties
  const label = p.city ?? p.name ?? p.state
  if (!label || label.trim().length < 2) return null
  return toCityOption(label, p.osm_id)
}

const PLACE_TYPES = new Set(['city', 'town', 'administrative', 'municipality'])

function isNominatimCity(result: NominatimResult): boolean {
  if (result.address?.country_code && result.address.country_code !== 'ru') return false
  if (result.class === 'place' && result.type && PLACE_TYPES.has(result.type)) return true
  if (result.class === 'boundary' && result.type === 'administrative' && (result.place_rank ?? 99) <= 16) return true
  if (result.addresstype === 'city' || result.addresstype === 'town') return true
  return false
}

function nominatimLabel(result: NominatimResult): string | null {
  if (result.name && result.name.trim().length >= 2 && isNominatimCity(result)) return result.name.trim()

  const a = result.address
  if (!a) return null

  if (a.city) return a.city.trim()
  if (a.town) return a.town.trim()
  if (a.municipality) return a.municipality.trim()
  if (a.state && (result.type === 'administrative' || result.addresstype === 'city')) return a.state.trim()

  return null
}

function toNominatimOptions(results: NominatimResult[]): CityOption[] {
  const seen = new Set<string>()
  const options: CityOption[] = []

  for (const result of results) {
    if (!isNominatimCity(result)) continue
    const label = nominatimLabel(result)
    if (!label) continue
    const key = label.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    options.push(toCityOption(label, result.place_id))
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

async function nominatimFetch(path: string, params: Record<string, string>) {
  const url = new URL(path, NOMINATIM)
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v)
  const res = await fetch(url, { headers: { 'Accept-Language': 'ru', 'User-Agent': USER_AGENT }, signal: AbortSignal.timeout(8000) })
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

  const data = (await nominatimFetch('/search', {
    q,
    countrycodes: 'ru',
    format: 'json',
    addressdetails: '1',
    limit: '20',
  })) as NominatimResult[]

  return toNominatimOptions(data)
}

async function detectCityByIp(): Promise<CityOption | null> {
  const res = await fetch('https://ipwho.is/', { signal: AbortSignal.timeout(4000) })
  if (!res.ok) return null
  const data = (await res.json()) as {
    success?: boolean
    country_code?: string
    city?: string
    latitude?: number
    longitude?: number
  }
  if (!data.success || data.country_code !== 'RU') return null

  if (data.latitude != null && data.longitude != null) {
    const city = await reverseGeocode(data.latitude, data.longitude)
    if (city) return city
  }

  if (data.city) {
    const match = getPopularCities().find((c) => c.label.toLowerCase() === data.city!.toLowerCase())
    if (match) return match
    const found = await searchCities(data.city)
    return found[0] ?? null
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

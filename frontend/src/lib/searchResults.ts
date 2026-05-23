export type SiteKind = 'ozon' | 'wildberries' | 'yandex' | 'other'

export type Product = {
  id: string
  name: string
  price: number
  brand?: string | null
  originalPrice?: number | null
  url?: string | null
  imageUrl?: string | null
}

export type SiteResult = {
  slug: string
  name: string
  kind: SiteKind
  products: Product[]
  logo?: string
  rating?: number
  reviewsLabel?: string
  error?: string | null
  sourceComplete?: boolean
}

export const MARKETPLACE_LOGOS = {
  ozon: 'https://upload.wikimedia.org/wikipedia/ru/e/ec/OZON_2019.svg',
  wildberries: 'https://upload.wikimedia.org/wikipedia/commons/4/41/Wildberries_2023_Pink.svg',
  yandexMarket: 'https://upload.wikimedia.org/wikipedia/ru/e/ec/%D0%9A%D1%80%D0%B0%D1%81%D0%BD%D1%8B%D0%B9_%D0%AF%D0%BD%D0%B4%D0%B5%D0%BA%D1%81_%D0%9C%D0%B0%D1%80%D0%BA%D0%B5%D1%82%2C_2024.svg',
} as const

export const MARKETPLACE_URLS = {
  ozon: 'https://www.ozon.ru/',
  wildberries: 'https://www.wildberries.ru/',
  yandex: 'https://market.yandex.ru/',
} as const

export function getMarketplaceUrl(kind: SiteKind): string | undefined {
  if (kind === 'other') return undefined
  return MARKETPLACE_URLS[kind]
}

export const siteResults: SiteResult[] = [
  {
    slug: 'ozon',
    name: 'OZON',
    kind: 'ozon',
    logo: MARKETPLACE_LOGOS.ozon,
    products: [
      { id: 'ozon-1', name: 'Беспроводная мышь Pro', price: 1890 },
      { id: 'ozon-2', name: 'Клавиатура компактная', price: 3490 },
      { id: 'ozon-3', name: 'USB-C кабель 2 м', price: 490 },
      { id: 'ozon-4', name: 'Ноутбук 14 дюймов', price: 58990 },
      { id: 'ozon-5', name: 'Подставка для ноутбука', price: 1290 },
      { id: 'ozon-6', name: 'Web-камера Full HD', price: 2290 },
    ],
  },
  {
    slug: 'wildberries',
    name: 'Wildberries',
    kind: 'wildberries',
    logo: MARKETPLACE_LOGOS.wildberries,
    products: [
      { id: 'wb-1', name: 'Худи базовое', price: 2190 },
      { id: 'wb-2', name: 'Рюкзак городской', price: 2690 },
      { id: 'wb-3', name: 'Кроссовки лёгкие', price: 4190 },
      { id: 'wb-4', name: 'Футболка хлопковая', price: 790 },
      { id: 'wb-5', name: 'Плед тёплый', price: 1590 },
      { id: 'wb-6', name: 'Органайзер для стола', price: 690 },
    ],
  },
  {
    slug: 'yandex-market',
    name: 'Yandex.Market',
    kind: 'yandex',
    logo: MARKETPLACE_LOGOS.yandexMarket,
    products: [
      { id: 'ym-1', name: 'Смартфон 128 ГБ', price: 28990 },
      { id: 'ym-2', name: 'Наушники с шумоподавлением', price: 6990 },
      { id: 'ym-3', name: 'Умная колонка', price: 5490 },
      { id: 'ym-4', name: 'Планшет 10 дюймов', price: 22990 },
      { id: 'ym-5', name: 'Внешний аккумулятор', price: 1790 },
      { id: 'ym-6', name: 'Роутер Wi-Fi 6', price: 4590 },
    ],
  },
  {
    slug: 'dns',
    name: 'DNS',
    kind: 'other',
    rating: 4.2,
    reviewsLabel: '61.2K отзывов на магазин',
    products: [
      { id: 'dns-1', name: 'Монитор 27 дюймов', price: 16990 },
      { id: 'dns-2', name: 'SSD 1 ТБ', price: 7290 },
      { id: 'dns-3', name: 'Игровая мышь', price: 2490 },
      { id: 'dns-4', name: 'Корпус Mini Tower', price: 3990 },
      { id: 'dns-5', name: 'Микрофон USB', price: 3290 },
    ],
  },
  {
    slug: 'mega-market',
    name: 'Мегамаркет',
    kind: 'other',
    rating: 3.5,
    reviewsLabel: '12.8K отзывов на магазин',
    products: [
      { id: 'mm-1', name: 'Кофемолка', price: 1990 },
      { id: 'mm-2', name: 'Электрочайник', price: 2890 },
      { id: 'mm-3', name: 'Настольная лампа', price: 1290 },
      { id: 'mm-4', name: 'Термокружка', price: 890 },
      { id: 'mm-5', name: 'Сумка для ноутбука', price: 2490 },
    ],
  },
]

export const mainSiteResults = siteResults.filter((site) => site.kind !== 'other')
export const otherSiteResults = siteResults.filter((site) => site.kind === 'other')

export function formatSiteRating(rating: number) {
  return `${rating.toFixed(1)}`
}

export function formatPrice(price: number) {
  return `${price.toLocaleString('ru-RU')} ₽`
}

export function getSiteBySlug(slug: string) {
  return siteResults.find((site) => site.slug === slug)
}

export function getProduct(siteSlug: string, productId: string) {
  const site = getSiteBySlug(siteSlug)
  if (!site) return null
  const product = site.products.find((item) => item.id === productId)
  if (!product) return null
  return { site, product }
}

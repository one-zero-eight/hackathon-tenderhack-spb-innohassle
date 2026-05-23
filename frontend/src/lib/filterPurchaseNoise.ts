import type { SuggestItem } from './yandexSuggest'

/** Границы «слова» для кириллицы (\\b в JS только для [A-Za-z0-9_]) */
const W = '(?:^|[\\s,.;:!?()\\[\\]«»"\'-])'
const WE = '(?:$|[\\s,.;:!?()\\[\\]«»"\'-])'

/**
 * Скрываем подсказки про площадки, цену, б/у и «где купить»,
 * но не режем строки только из‑за слова «купить» (могут быть модели: «… hp», «… asus»).
 */
const PURCHASE_NOISE = [
  new RegExp(`${W}б/у${WE}`, 'iu'),
  new RegExp(`${W}бу${WE}`, 'iu'),
  new RegExp(`${W}б\\.?\\s?у\\.?${WE}`, 'iu'),
  new RegExp(`${W}вторич(?:ка|ный|ное|ные)?${WE}`, 'iu'),

  /(?:^|\s)на\s+(?:авито|юле|юлу|юла|озон(?:е)?|wildberries|вайлдберриз|wb|яндекс[\s.-]?маркет(?:е)?|маркетплейсе|aliexpress|алиэкспресс|youla|ламода|сбермегамаркет(?:е)?|мегамаркет(?:е)?|dns|мвидео|ситилинк|связном|горбушк(?:е|и)?)(?:\s|$|[.,])/iu,
  new RegExp(`${W}(?:авито|youla|юла|ozon|озон|wildberries|вайлдберриз|маркетплейс)${WE}`, 'iu'),

  new RegExp(`${W}(?:цена|стоимость|скидк|акци[яи]|промокод|распродаж|недорого|дешевле|дешёв)${WE}`, 'iu'),
  /(?:^|\s)в\s+рассроч\w*/iu,
  /(?:^|\s)рассроч\w*(?:\s|$|[.,])/iu,
  /(?:^|\s)цена\s+в(?:\s|$)/iu,
  /(?:^|\s)сколько\s+стоит(?:\s|$|[.,])/iu,

  // «купить … в москве / в польше», «… москва» как город покупки
  /(?:^|\s)в\s+(?:москве|москву|питере|питер|спб|санкт-петербурге|польше|казани|новосибирске|екатеринбурге|донецке|краснодаре|ростове)(?:\s|$|[.,])/iu,
  /(?:^|\s)(?:москв[аеу]|питер(?:е)?|спб)(?:\s|$|[.,])/iu,
]

export function isPurchaseNoise(text: string): boolean {
  const normalized = text.trim().toLowerCase()
  if (!normalized) return false
  return PURCHASE_NOISE.some((re) => re.test(normalized))
}

export function filterPurchaseNoise(items: SuggestItem[]): {
  items: SuggestItem[]
  hiddenCount: number
} {
  const kept = items.filter((item) => !isPurchaseNoise(item.text))
  return { items: kept, hiddenCount: items.length - kept.length }
}

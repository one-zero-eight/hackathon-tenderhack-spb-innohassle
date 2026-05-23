/** Границы «слова» для кириллицы (\\b в JS только для [A-Za-z0-9_]) */
const W = '(?:^|[\\s,.;:!?()\\[\\]«»"\'-])'
const WE = '(?:$|[\\s,.;:!?()\\[\\]«»"\'-])'

const COUNTRY_LOCATIVE =
  'россии|россию|китае|турции|беларуси|белоруссии|казахстане|украине|германии|франции|италии|испании|америке|сша|японии|корее|индии|польше|англии|великобритании|таиланде|вьетнаме|греции|чехии|австрии|швейцарии|нидерландах|голландии|бельгии|швеции|норвегии|финляндии|дании|израиле|армении|грузии|узбекистане|кыргызстане|киргизии|азербайджане|молдове|латвии|литве|эстонии|европе|снг|дубае|оаэ|египте|мексике|бразилии|канаде|австралии|днр|лнр|луганске|мариуполе|владивостоке'

const GEO_IN = '(?:в|во)'

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
  /(?:^|\s)в\s+(?:москве|москву|питере|питер|спб|санкт-петербурге|казани|новосибирске|екатеринбурге|донецке|краснодаре|ростове)(?:\s|$|[.,])/iu,
  /(?:^|\s)(?:москв[аеу]|питер(?:е)?|спб)(?:\s|$|[.,])/iu,
  new RegExp(`${W}(?:руб(?:ль|ля|лей|\\.?)?|₽|rub|usd|eur|cny|gbp|доллар(?:а|ов|у|е)?|евро|юан(?:ь|я|ей)?|фунт(?:а|ов|ов)?)${WE}`, 'iu'),
  /(?:^|\s)\d[\d\s,.]*(?:руб(?:\\.?|л(?:ь|я|ей)?)?|₽|usd|eur|cny)(?:\s|$|[.,])/iu,
  /(?:^|\s)(?:курс|обмен)(?:\s+(?:валют|доллар|евро|рубл))?(?:\s|$|[.,])/iu,
  new RegExp(
    `${W}(?:сбербанк|сбер|втб|альфа[-\\s]?банк|тинькофф|т[-\\s]?банк|tbank|газпромбанк|россельхозбанк|рсхб|открыти[ея]|почта[-\\s]?банк|райффайзен|raiffeisen|юникредит|росбанк|мкб|модульбанк|хоум[-\\s]?кредит|home[-\\s]?credit|совкомбанк|sovcombank|промсвязьбанк|псб|росгосстрах|банк\\s+россии)${WE}`,
    'iu',
  ),
  new RegExp(`(?:^|\\s)купить\\s+${GEO_IN}\\s+(?:${COUNTRY_LOCATIVE})(?:\\s|$|[.,])`, 'iu'),
  new RegExp(`^купить\\s+${GEO_IN}\\s+(?:${COUNTRY_LOCATIVE})$`, 'iu'),
  new RegExp(`^${GEO_IN}\\s+(?:${COUNTRY_LOCATIVE})(?:\\s+купить)?$`, 'iu'),
]

function isPurchaseNoise(text: string): boolean {
  const normalized = text.trim().toLowerCase()
  if (!normalized) return false
  return PURCHASE_NOISE.some((re) => re.test(normalized))
}

export function stripTrailingPurchaseWord(text: string): string {
  return text.replace(/\s+купить$/iu, '').trim()
}

export function stripGeoPurchaseSuffix(text: string): string {
  const buyIn = new RegExp(`\\s+купить\\s+${GEO_IN}\\s+(?:${COUNTRY_LOCATIVE})$`, 'iu')
  const inCountry = new RegExp(`\\s+${GEO_IN}\\s+(?:${COUNTRY_LOCATIVE})(?:\\s+купить)?$`, 'iu')
  return text.replace(buyIn, '').replace(inCountry, '').trim()
}

export function filterPurchaseNoise(items: string[]): string[] {
  return items.filter((text) => !isPurchaseNoise(text))
}

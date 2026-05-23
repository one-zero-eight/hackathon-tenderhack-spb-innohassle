import { MARKETPLACE_LOGOS } from '@/lib/searchResults'
import { IoChevronDown, IoLocationOutline, IoSearch } from 'react-icons/io5'

const mockSources = [
  { name: 'Яндекс Маркет', logo: MARKETPLACE_LOGOS.yandexMarket, count: '127 предложений', active: true },
  { name: 'OZON', logo: MARKETPLACE_LOGOS.ozon, count: '98 предложений', active: false },
  { name: 'Wildberries', logo: MARKETPLACE_LOGOS.wildberries, count: '84 предложения', active: false },
  { name: 'Другие источники', count: '66 предложений', active: false },
] as const

const mockProducts = [
  { name: 'Ноутбук Lenovo ThinkPad E15', price: '45 990 ₽', logo: MARKETPLACE_LOGOS.yandexMarket },
  { name: 'Lenovo ThinkPad E15 G4', price: '47 500 ₽', logo: MARKETPLACE_LOGOS.ozon },
  { name: 'ThinkPad E15 15.6" IPS', price: '44 200 ₽', logo: MARKETPLACE_LOGOS.wildberries },
] as const

export default function LandingSearchPreview() {
  return (
    <div
      id="preview"
      className="border-gray-blue/70 w-full max-w-xl justify-self-center overflow-hidden rounded-xl border bg-white shadow-[0_20px_50px_-12px_rgba(38,75,130,0.25)] lg:justify-self-end"
    >
      <div className="border-gray-blue/50 flex flex-col gap-2 border-b bg-[#f8fafc] p-3 sm:flex-row sm:items-stretch sm:gap-2 sm:p-3">
        <label className="border-gray-blue/60 flex min-w-0 flex-1 items-center gap-2 rounded-lg border bg-white px-3 py-2.5">
          <IoSearch className="text-gray shrink-0" size={18} aria-hidden />
          <span className="truncate text-sm text-black">Ноутбук Lenovo ThinkPad</span>
        </label>
        <div className="flex shrink-0 gap-2">
          <div className="border-gray-blue/60 flex items-center gap-1.5 rounded-lg border bg-white px-3 py-2.5 text-sm text-black">
            <IoLocationOutline className="text-gray shrink-0" size={16} aria-hidden />
            <span className="whitespace-nowrap">Москва</span>
            <IoChevronDown className="text-gray shrink-0" size={14} aria-hidden />
          </div>
          <button type="button" className="bg-main-blue rounded-lg px-5 py-2.5 text-sm font-semibold whitespace-nowrap text-white">
            Найти
          </button>
        </div>
      </div>

      <div className="grid min-h-[18rem] md:grid-cols-[10.5rem_1fr]">
        <aside className="border-gray-blue/50 border-b bg-[#f4f7fb] p-3 md:border-r md:border-b-0">
          <p className="text-gray mb-3 text-[10px] font-bold tracking-widest uppercase">Источники</p>
          <ul className="space-y-2">
            {mockSources.map((source) => (
              <li
                key={source.name}
                className={`rounded-lg px-2.5 py-2 ${source.active ? 'border-main-blue/30 border bg-white shadow-sm' : ''}`}
              >
                <div className="flex min-w-0 items-center gap-2">
                  {'logo' in source && source.logo ? (
                    <img src={source.logo} alt="" className="h-3.5 w-auto max-w-[3.75rem] shrink-0 object-contain object-left" />
                  ) : null}
                  <span className={`truncate text-xs leading-tight ${source.active ? 'text-main-blue font-semibold' : 'text-gray'}`}>{source.name}</span>
                </div>
                <p className={`mt-1 text-[10px] leading-tight ${source.active ? 'text-main-blue/80' : 'text-gray'}`}>{source.count}</p>
              </li>
            ))}
          </ul>
        </aside>

        <div className="p-3 md:p-4">
          <p className="text-gray mb-3 text-[10px] font-bold tracking-widest uppercase">Лучшие предложения</p>
          <ul className="space-y-2.5">
            {mockProducts.map((product) => (
              <li key={product.name} className="border-gray-blue/40 flex items-center gap-3 rounded-lg border bg-[#fafbfd] p-2.5">
                <span
                  className="h-11 w-14 shrink-0 rounded border border-[#dce4ef] bg-linear-to-br from-[#e8eef5] to-[#cfd9e8]"
                  aria-hidden
                />
                <div className="min-w-0 flex-1">
                  <p className="line-clamp-2 text-xs leading-snug font-medium text-black">{product.name}</p>
                  <p className="text-main-blue mt-0.5 text-sm font-bold">{product.price}</p>
                </div>
                <img src={product.logo} alt="" className="h-4 w-auto max-w-[3.25rem] shrink-0 object-contain" />
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="border-gray-blue/50 text-gray flex flex-wrap items-center justify-between gap-2 border-t bg-[#f4f7fb] px-4 py-2.5 text-[11px]">
        <span className="flex items-center gap-2">
          <span className="bg-green inline-block h-2 w-2 rounded-full" aria-hidden />
          Идёт поиск и сбор данных…
        </span>
        <span className="font-medium">Найдено 375 предложений</span>
      </div>
    </div>
  )
}

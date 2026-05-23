import { LandingDitherBackground } from '@/components/ui/hero-dithering-card'
import { createFileRoute, Link } from '@tanstack/react-router'
import { HiOutlineArrowLongRight } from 'react-icons/hi2'

export const Route = createFileRoute('/')({
  component: LandingPage,
})

function LandingPage() {
  return (
    <LandingDitherBackground className="flex min-h-screen flex-col justify-center bg-white text-black" accentColor="#264b82">
      <div className="border-gray-blue/50 ml-[15vw] max-w-3xl rounded-3xl border bg-white p-12 shadow-lg shadow-black/10 backdrop-blur-xs">
        <h1 className="text-main-blue mb-5 text-[1.85rem] leading-[1.15] font-bold tracking-tight text-balance sm:text-4xl lg:text-[2.75rem]">Умный поиск цен по&nbsp;Рунету</h1>
        <p className="text-pale-black mb-2 text-base font-medium">Собираем предложения с маркетплейсов и открытых источников, чтобы вы принимали решения быстрее.</p>

        <div className="mt-15 flex flex-wrap gap-3">
          <Link to="/search" className="bg-red hover:bg-dark-red flex items-center gap-3 rounded-lg px-6 py-3 text-sm font-semibold text-white transition-colors">
            Начать поиск
            <HiOutlineArrowLongRight className="size-7" />
          </Link>
        </div>

        {/* <div id="sources">
          <p className="text-gray mb-2 text-xs font-medium tracking-wide uppercase">Источники данных</p>
          <div className="flex flex-wrap gap-2">
            {[
              { label: 'Яндекс Маркет', logo: MARKETPLACE_LOGOS.yandexMarket },
              { label: 'OZON', logo: MARKETPLACE_LOGOS.ozon },
              { label: 'Wildberries', logo: MARKETPLACE_LOGOS.wildberries },
            ].map((item) => (
              <span key={item.label} className="border-gray-blue/60 flex h-11 min-w-30 items-center justify-center rounded-lg border bg-white/90 px-4 backdrop-blur-sm">
                <img src={item.logo} alt={item.label} className="logo-tint-blue h-4.5 w-auto max-w-full object-contain" />
              </span>
            ))}
          </div>  
        </div> */}
      </div>
    </LandingDitherBackground>
  )
}

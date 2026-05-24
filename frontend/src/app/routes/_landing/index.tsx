import { MARKETPLACE_LOGOS } from '@/lib/searchResults'
import { startViewTransition } from '@/lib/viewTransition'
import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { HiOutlineArrowLongRight } from 'react-icons/hi2'
import { Fragment } from 'react/jsx-runtime'

export const Route = createFileRoute('/_landing/')({
  component: LandingPage,
})

function LandingPage() {
  const navigate = useNavigate()

  const goToSearch = () => {
    startViewTransition(() => {
      void navigate({ to: '/search' })
    })
  }

  return (
    <Fragment>
      <a href="https://zakupki.mos.ru/" target="_blank" rel="noopener noreferrer" className="absolute top-10 left-1/2 z-10 -translate-x-1/2 pr-3">
        <img src="/zakupki.svg" alt="zakupki" className="h-9" />
      </a>
      <div className="landing-page-content flex min-h-screen flex-col items-center justify-center">
        <div className="flex flex-col items-center justify-center">
          <h1 className="text-main-blue mb-5 text-3xl leading-[1.15] font-bold tracking-tight text-balance sm:text-4xl lg:text-7xl">Умный поиск цен по Рунету</h1>
          <p className="mb-10 max-w-xl text-center text-base font-medium text-black">Собираем предложения с маркетплейсов и открытых источников, чтобы вы принимали решения быстрее.</p>

          <button type="button" onClick={goToSearch} className="bg-red hover:bg-dark-red flex w-fit items-center gap-3 rounded-lg px-6 py-2 text-sm font-semibold text-white transition-colors">
            Начать поиск
            <HiOutlineArrowLongRight className="size-7" />
          </button>
        </div>
      </div>
      <div className="absolute bottom-20 left-1/2 z-10 flex -translate-x-1/2 flex-wrap gap-2">
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
    </Fragment>
  )
}

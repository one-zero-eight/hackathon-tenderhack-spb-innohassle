import { LandingDitherBackground } from '@/components/ui/hero-dithering-card'
import { createFileRoute, Outlet, useRouterState } from '@tanstack/react-router'

const LANDING_ACCENT = '#264b82'
const SEARCH_ACCENT = '#afc4de'

export const Route = createFileRoute('/_landing')({
  component: LandingLayout,
})

function LandingLayout() {
  const isSearch = useRouterState({ select: (s) => s.location.pathname === '/search' })
  const accentColor = isSearch ? SEARCH_ACCENT : LANDING_ACCENT

  return (
    <LandingDitherBackground className="min-h-screen bg-white text-black" accentColor={accentColor}>
      <Outlet />
    </LandingDitherBackground>
  )
}

import NotFoundPage from '@/components/pages/NotFoundPage'
import { createRootRoute, Outlet } from '@tanstack/react-router'

const RootLayout = () => (
  <div className="flex min-h-screen flex-col">
    <Outlet />
  </div>
)

export const Route = createRootRoute({
  component: RootLayout,
  notFoundComponent: () => <NotFoundPage />,
})

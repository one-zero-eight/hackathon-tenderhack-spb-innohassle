import Navbar from '@/components/shared/Navbar'
import { createRootRoute, Outlet } from '@tanstack/react-router'

const RootLayout = () => (
  <div className="flex h-screen flex-col">
    <Navbar />
    <Outlet />
  </div>
)

export const Route = createRootRoute({ component: RootLayout })

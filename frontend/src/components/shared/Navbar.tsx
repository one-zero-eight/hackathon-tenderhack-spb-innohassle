import { Link } from '@tanstack/react-router'

export default function Navbar() {
  return (
    <div className="flex w-full items-center justify-start gap-3 p-3">
      <Link to="/">Home</Link>
      <Link to="/previews">Previews</Link>
    </div>
  )
}

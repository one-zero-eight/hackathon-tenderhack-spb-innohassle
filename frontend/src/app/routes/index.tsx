import { $api } from '@/api'
import Link from '@/components/ui/Link'
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/')({
  component: Index,
})

function Index() {
  const { data } = $api.useQuery('get', '/users')
  console.log(data)

  return (
    <div className="flex flex-col items-center gap-2 p-4">
      <Link to="/previews">Previews</Link>
    </div>
  )
}

import { Link } from '@tanstack/react-router'
import Button from '@/components/ui/Button'
import { cn } from '@/lib/cn'

interface NotFoundPageProps {
  title?: string
  message?: string
  backTo?: string
  backLabel?: string
  className?: string
}

export default function NotFoundPage({ title = '404 - Not Found', message = 'Запрашиваемая страница не найдена', backTo = '/', backLabel = 'Вернуться назад', className }: NotFoundPageProps) {
  return (
    <div className={cn('flex min-h-80 flex-col items-center justify-center gap-3 px-3 py-4 sm:gap-4 sm:p-4', className)}>
      <h2 className="text-xl font-semibold sm:text-2xl">{title}</h2>
      <p className="text-center text-sm text-gray-600 sm:text-base">{message}</p>
      <Link to={backTo}>
        <Button variant="outline" size="sm">
          {backLabel}
        </Button>
      </Link>
    </div>
  )
}

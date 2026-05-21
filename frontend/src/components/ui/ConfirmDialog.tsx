import { Dialog, DialogBackdrop, DialogPanel, DialogTitle, Description } from '@headlessui/react'
import Button from './Button'
import { useEffect } from 'react'

interface ConfirmDialogProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  title: string
  description: string
  confirmLabel?: string
  cancelLabel?: string
  variant?: 'danger' | 'default'
  isLoading?: boolean
}

export default function ConfirmDialog({ isOpen, onClose, onConfirm, title, description, confirmLabel = 'Подтвердить', cancelLabel = 'Отмена', variant = 'default', isLoading = false }: ConfirmDialogProps) {
  useEffect(() => {
    if (isOpen) {
      const dialog = document.querySelector('[role="dialog"]')
      const confirmButton = dialog?.querySelector('button:last-of-type') as HTMLElement
      if (confirmButton) {
        setTimeout(() => confirmButton.focus(), 100)
      }
    }
  }, [isOpen])

  return (
    <Dialog open={isOpen} onClose={onClose} className="relative z-50">
      <DialogBackdrop className="fixed inset-0 bg-black/30" />
      <div className="fixed inset-0 flex w-screen items-center justify-center p-4">
        <DialogPanel className="max-w-lg space-y-4 rounded-xl bg-white p-8">
          <DialogTitle className="text-xl font-bold">{title}</DialogTitle>
          <Description>{description}</Description>
          <div className="flex items-center justify-end gap-4">
            <Button size="sm" variant="outline" onClick={onClose} disabled={isLoading}>
              {cancelLabel}
            </Button>
            <Button size="sm" variant={variant === 'danger' ? 'primary' : 'primary'} onClick={onConfirm} disabled={isLoading}>
              {isLoading ? 'Обработка...' : confirmLabel}
            </Button>
          </div>
        </DialogPanel>
      </div>
    </Dialog>
  )
}

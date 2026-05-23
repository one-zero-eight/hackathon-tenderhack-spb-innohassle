import { cn } from '@/lib/cn'
import { useEffect, useRef, useState } from 'react'
import { IoChevronDown, IoChevronUp, IoSwapVertical } from 'react-icons/io5'

export type SortOption = {
  value: string
  label: string
}

type SortDropdownProps = {
  options: SortOption[]
  value: string
  onChange: (value: string) => void
  className?: string
  radioRingSelectedClassName?: string
  radioDotSelectedClassName?: string
}

export default function SortDropdown({
  options,
  value,
  onChange,
  className,
  radioRingSelectedClassName = 'border-main-blue',
  radioDotSelectedClassName = 'bg-main-blue',
}: SortDropdownProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const selected = options.find((option) => option.value === value)

  useEffect(() => {
    if (!open) return

    const onPointerDown = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [open])

  return (
    <div ref={rootRef} className={cn('relative w-fit', className)}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="bg-pale-blue/45 flex cursor-pointer items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-black"
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        <IoSwapVertical className="text-gray shrink-0" size={18} aria-hidden />
        <span className="whitespace-nowrap">{selected?.label ?? 'Сортировка'}</span>
        {open ? <IoChevronUp className="text-gray shrink-0" size={16} aria-hidden /> : <IoChevronDown className="text-gray shrink-0" size={16} aria-hidden />}
      </button>

      {open && (
        <div className="border-gray-blue/60 absolute top-full left-0 z-50 mt-2 min-w-72 overflow-hidden rounded-2xl border bg-white py-1 shadow-lg" role="listbox">
          {options.map((option) => {
            const isSelected = option.value === value

            return (
              <button
                key={option.value}
                type="button"
                role="option"
                aria-selected={isSelected}
                onClick={() => {
                  onChange(option.value)
                  setOpen(false)
                }}
                className="hover:bg-pale-blue/50 flex w-full cursor-pointer items-center gap-3 px-4 py-3 text-left text-sm text-black transition-colors"
              >
                <span
                  className={cn(
                    'flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 transition-colors',
                    isSelected ? radioRingSelectedClassName : 'border-gray-blue',
                  )}
                  aria-hidden
                >
                  {isSelected && <span className={cn('h-2.5 w-2.5 rounded-full', radioDotSelectedClassName)} />}
                </span>
                <span>{option.label}</span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

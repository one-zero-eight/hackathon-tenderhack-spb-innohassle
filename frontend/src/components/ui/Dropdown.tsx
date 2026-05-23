import { cn } from '@/lib/cn'
import cva, { type VariantProps } from '@/lib/cva'
import { forwardRef, useState, useRef, useEffect, useCallback, type ReactNode } from 'react'
import { IoCheckmark, IoChevronUp } from 'react-icons/io5'
import Input from '@/components/ui/Input'

interface Option {
  id: number
  value: string
  label: string
}

const dropdownVariants = cva('cursor-pointer text-black', {
  variants: {
    variant: {
      filled: 'bg-pale-blue',
      ghost: 'bg-transparent',
    },
    size: {
      sm: 'text-sm',
      md: 'text-md',
      lg: 'text-lg',
    },
  },
  default: {
    variant: 'filled',
  },
})

const dropdownShellVariants = cva('', {
  variants: {
    variant: {
      filled: 'border-gray-blue border',
      ghost: 'border-0',
    },
  },
  default: {
    variant: 'filled',
  },
})

type DropdownProps = VariantProps<typeof dropdownVariants> &
  VariantProps<typeof dropdownShellVariants> & {
    label?: string
    options: Option[]
    onSelect: (value: string) => void
    className?: string
    placeholder?: string
    value?: string
    displayLabel?: string
    searchable?: boolean
    searchPlaceholder?: string
    searchValue?: string
    onSearchChange?: (value: string) => void
    emptyMessage?: string
    trailingIcon?: ReactNode
    menuClassName?: string
    menuHeader?: ReactNode
    searchLeadingIcon?: ReactNode
    searchSize?: 'sm' | 'md' | 'lg'
  }

const Dropdown = forwardRef<HTMLDivElement, DropdownProps>(
  (
    {
      className,
      options,
      label,
      onSelect,
      size,
      variant,
      placeholder,
      value: controlledValue,
      displayLabel,
      searchable,
      searchPlaceholder = 'Поиск…',
      searchValue = '',
      onSearchChange,
      emptyMessage = 'Ничего не найдено',
      trailingIcon,
      menuClassName,
      menuHeader,
      searchLeadingIcon,
      searchSize = 'sm',
      ...props
    },
    ref,
  ) => {
    const [isOpen, setIsOpen] = useState(false)
    const [selectedValue, setSelectedValue] = useState<string | undefined>(controlledValue)
    const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)
    const dropdownRef = useRef<HTMLDivElement>(null)

    const setRefs = useCallback(
      (node: HTMLDivElement | null) => {
        dropdownRef.current = node
        if (typeof ref === 'function') {
          ref(node)
        } else if (ref) {
          ref.current = node
        }
      },
      [ref],
    )

    // Sync controlled value to internal state
    useEffect(() => {
      if (controlledValue !== undefined) {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setSelectedValue(controlledValue)
      }
    }, [controlledValue])

    useEffect(() => {
      const handleClickOutside = (event: MouseEvent) => {
        if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
          setIsOpen(false)
        }
      }

      if (isOpen) {
        document.addEventListener('mousedown', handleClickOutside)
        return () => document.removeEventListener('mousedown', handleClickOutside)
      }
    }, [isOpen])

    const selectedOption = options.find((opt) => opt.value === selectedValue)
    const displayText = selectedOption?.label ?? displayLabel ?? placeholder ?? 'Select an option'

    const handleSelect = (option: Option) => {
      setSelectedValue(option.value)
      onSelect(option.value)
      setIsOpen(false)
      setHoveredIndex(null)
    }

    return (
      <div ref={setRefs} className="relative" {...props}>
        {label && <p className="text-md mb-2 text-black">{label}</p>}
        <div className={cn(dropdownShellVariants({ variant }), className)}>
          <button type="button" onClick={() => setIsOpen(!isOpen)} className={cn('text-pale-black text-md flex w-full items-center gap-2 px-3 py-2', dropdownVariants({ variant, size }))}>
            <IoChevronUp className={cn('shrink-0 transition-transform duration-200', isOpen ? 'rotate-0' : 'rotate-180')} size={16} />
            <span className="min-w-0 flex-1 truncate text-left">{displayText}</span>
            {trailingIcon && <span className="text-gray flex shrink-0 items-center">{trailingIcon}</span>}
          </button>

          {isOpen && (
            <div
              className={cn(
                'absolute top-full z-50 flex max-h-80 flex-col overflow-hidden bg-white shadow-lg',
                variant === 'filled' ? 'border-gray-blue right-0 left-0 border border-t-0' : 'border-gray-blue/60 right-0 left-auto mt-2 rounded-2xl border shadow-xl',
                menuClassName,
              )}
            >
              {searchable && (
                <div className={cn('shrink-0 p-3', variant === 'filled' ? 'border-gray-blue border-b' : 'border-gray-blue/40 bg-pale-blue/30 border-b')} onMouseDown={(e) => e.stopPropagation()}>
                  <Input size={searchSize} variant="fill" placeholder={searchPlaceholder} value={searchValue} onChange={(e) => onSearchChange?.(e.target.value)} leadingIcon={searchLeadingIcon} className="rounded-xl border-0" />
                </div>
              )}
              {menuHeader}
              <div className="flex min-h-0 flex-1 flex-col gap-1.5 overflow-y-auto px-1.5 py-2">
                {options.length === 0 && <p className="text-gray px-3 py-3 text-sm">{emptyMessage}</p>}
                {options.map((option, index) => {
                  const isSelected = option.value === selectedValue
                  const isHovered = hoveredIndex === index

                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() => handleSelect(option)}
                      onMouseEnter={() => setHoveredIndex(index)}
                      onMouseLeave={() => setHoveredIndex(null)}
                      className={cn(
                        'flex w-full cursor-pointer items-center gap-2.5 rounded-xl px-3 py-2.5 text-left text-sm transition-colors',
                        isSelected ? 'bg-pale-blue/70 text-main-blue font-medium' : 'text-black',
                        !isSelected && isHovered ? 'text-main-blue' : undefined,
                        dropdownVariants({ size }),
                      )}
                    >
                      <span className="flex h-5 w-5 shrink-0 items-center justify-center" aria-hidden>
                        {isSelected ? <IoCheckmark className="text-main-blue" size={16} /> : null}
                      </span>
                      <span className="min-w-0 flex-1 truncate">{option.label}</span>
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    )
  },
)

Dropdown.displayName = 'Dropdown'
export default Dropdown

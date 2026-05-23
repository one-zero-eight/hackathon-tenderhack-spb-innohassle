import { cn } from '@/lib/cn'
import cva, { type VariantProps } from '@/lib/cva'
import { forwardRef, useState, useRef, useEffect, useCallback, type ReactNode } from 'react'
import { IoChevronUp } from 'react-icons/io5'
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
            <div className={cn('absolute top-full z-50 max-h-80 overflow-y-auto bg-white shadow-lg', variant === 'filled' ? 'border-gray-blue right-0 left-0 border border-t-0' : 'right-0 left-auto', menuClassName)}>
              {searchable && (
                <div className={cn('p-3', variant === 'filled' ? 'border-gray-blue border-b' : undefined)} onMouseDown={(e) => e.stopPropagation()}>
                  <Input size={searchSize} variant="fill" placeholder={searchPlaceholder} value={searchValue} onChange={(e) => onSearchChange?.(e.target.value)} />
                </div>
              )}
              {options.length === 0 && <p className="text-md text-gray px-4 py-3">{emptyMessage}</p>}
              {options.map((option, index) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => handleSelect(option)}
                  onMouseEnter={() => setHoveredIndex(index)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  className={cn('text-md hover:text-main-blue w-full cursor-pointer px-4 py-2.5 text-left text-black transition-colors', hoveredIndex === index ? 'text-main-blue' : undefined, dropdownVariants({ size }))}
                >
                  {option.label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  },
)

Dropdown.displayName = 'Dropdown'
export default Dropdown

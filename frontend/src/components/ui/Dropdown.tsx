import { cn } from '@/lib/cn'
import cva, { type VariantProps } from '@/lib/cva'
import { forwardRef, useState, useRef, useEffect, useCallback } from 'react'
import { IoChevronUp } from 'react-icons/io5'

interface Option {
  id: number
  value: string
  label: string
}

const dropdownVariants = cva('cursor-pointer text-black', {
  variants: {
    size: {
      sm: 'text-sm',
      md: 'text-md',
      lg: 'text-lg',
    },
  },
})

type DropdownProps = VariantProps<typeof dropdownVariants> & {
  label?: string
  options: Option[]
  onSelect: (value: string) => void
  className?: string
  placeholder?: string
  value?: string
}

const Dropdown = forwardRef<HTMLDivElement, DropdownProps>(({ className, options, label, onSelect, size, placeholder, value: controlledValue, ...props }, ref) => {
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
  const displayText = selectedOption?.label || placeholder || 'Select an option'

  const handleSelect = (option: Option) => {
    setSelectedValue(option.value)
    onSelect(option.value)
    setIsOpen(false)
    setHoveredIndex(null)
  }

  return (
    <div ref={setRefs} className={cn('relative', className)} {...props}>
      {label && <p className="text-md mb-2 text-black">{label}</p>}
      <div className="border-gray-blue border">
        <button type="button" onClick={() => setIsOpen(!isOpen)} className={cn('bg-pale-blue text-pale-black text-md flex w-full items-center justify-between px-3 py-2', dropdownVariants({ size }))}>
          <span className="text-left">{displayText}</span>
          <IoChevronUp className={cn('transition-transform duration-200', isOpen ? 'rotate-0' : 'rotate-180')} size={16} />
        </button>

        {isOpen && (
          <div className="border-gray-blue absolute top-full right-0 left-0 z-50 border border-t-0 bg-white shadow-lg">
            {options.map((option, index) => (
              <button
                key={option.id}
                type="button"
                onClick={() => handleSelect(option)}
                onMouseEnter={() => setHoveredIndex(index)}
                onMouseLeave={() => setHoveredIndex(null)}
                className={cn('text-md hover:text-main-blue w-full cursor-pointer px-3 py-2 text-left text-black transition-colors', hoveredIndex === option.id ? 'text-main-blue' : undefined, dropdownVariants({ size }))}
              >
                {option.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
})

Dropdown.displayName = 'Dropdown'
export default Dropdown

import { cn } from '@/lib/cn'
import cva, { type VariantProps } from '@/lib/cva'
import { forwardRef, useState, useEffect, useRef, type InputHTMLAttributes } from 'react'

const checkboxVariants = cva('', {
  variants: {
    size: {
      sm: 'w-4 h-4',
      md: 'w-5 h-5',
      lg: 'w-6 h-6',
    },
  },
  default: {
    size: 'md',
  },
})

type CheckboxPropsVariants = VariantProps<typeof checkboxVariants>
type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'size' | 'type'> &
  CheckboxPropsVariants & {
    label?: string
  }

const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(({ className, size, label, checked: controlledChecked, onChange, defaultChecked, ...props }, ref) => {
  const [internalChecked, setInternalChecked] = useState(defaultChecked ?? false)
  const inputRef = useRef<HTMLInputElement>(null)
  const isControlled = controlledChecked !== undefined
  const checked = isControlled ? controlledChecked : internalChecked

  // Merge refs
  useEffect(() => {
    if (typeof ref === 'function') {
      ref(inputRef.current)
    } else if (ref) {
      ref.current = inputRef.current
    }
  }, [ref])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.stopPropagation()
    // Don't prevent default - we need the input to update naturally
    // The checked value from the event is the new state after the click
    if (!isControlled) {
      setInternalChecked(e.target.checked)
    }
    // Call onChange - parent can read e.target.checked for the new value
    onChange?.(e)
  }

  return (
    <label className="group flex cursor-pointer items-center gap-2">
      <div className="relative">
        <input ref={inputRef} type="checkbox" checked={checked} onChange={handleChange} className="peer sr-only" {...props} />
        <div
          className={cn(
            'relative flex items-center justify-center border transition-colors duration-200',
            'peer-checked:bg-red peer-checked:border-red',
            checked ? 'bg-red border-red' : 'border-pale-blue bg-pale-blue',
            checkboxVariants({ size }),
            className,
          )}
        >
          {checked && (
            <svg className={cn('pointer-events-none', size === 'sm' ? 'h-3 w-3' : size === 'lg' ? 'h-4 w-4' : 'h-3.5 w-3.5')} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
              <path d="M5 13l4 4L19 7" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </div>
      </div>
      {label && <span className="text-md text-black select-none">{label}</span>}
    </label>
  )
})

Checkbox.displayName = 'Checkbox'
export default Checkbox

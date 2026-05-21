import { cn } from '@/lib/cn'
import cva, { type VariantProps } from '@/lib/cva'
import { forwardRef, type InputHTMLAttributes } from 'react'

const radioVariants = cva('', {
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

type RadioPropsVariants = VariantProps<typeof radioVariants>
type RadioProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'size' | 'type'> &
  RadioPropsVariants & {
    label?: string
  }

const Radio = forwardRef<HTMLInputElement, RadioProps>(({ className, size, label, checked, onChange, ...props }, ref) => {
  return (
    <label className="group flex cursor-pointer items-center gap-2">
      <div className="relative">
        <input ref={ref} type="radio" checked={checked} onChange={onChange} className="peer sr-only" {...props} />
        <div className={cn('flex items-center justify-center rounded-full border-2 transition-colors duration-200', 'peer-checked:bg-red peer-checked:border-red', 'border-light-gray bg-white', radioVariants({ size }), className)}>
          {checked && <div className={cn('rounded-full bg-white', size === 'sm' ? 'h-2 w-2' : size === 'lg' ? 'h-3 w-3' : 'h-2.5 w-2.5')} />}
        </div>
      </div>
      {label && <span className="text-md text-black select-none">{label}</span>}
    </label>
  )
})

Radio.displayName = 'Radio'
export default Radio

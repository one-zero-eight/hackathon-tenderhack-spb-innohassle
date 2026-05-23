import { cn } from '@/lib/cn'
import cva, { type VariantProps } from '@/lib/cva'
import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'

const inputVariants = cva('w-full border-2 border-pale-blue text-md placeholder:gray transition-colors focus:outline-none disabled:cursor-not-allowed disabled:opacity-50', {
  variants: {
    variant: {
      outline: 'text-gray bg-white',
      fill: 'bg-pale-blue',
      disabled: 'bg-secondary cursor-not-allowed',
    },
    size: {
      sm: 'px-2 py-1 text-xs',
      md: 'px-3 py-2 text-sm',
      lg: 'px-4 py-2.5 text-base',
      xl: 'px-5 py-3 text-lg',
    },
  },
  default: {
    size: 'md',
  },
})

type InputPropsVariants = VariantProps<typeof inputVariants>
type InputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> & InputPropsVariants & { label?: string | null; leadingIcon?: ReactNode }

const Input = forwardRef<HTMLInputElement, InputProps>(({ className, variant, size, label = null, disabled, leadingIcon, ...props }, ref) => {
  const resolvedVariant = disabled ? 'disabled' : variant
  const fieldClass = inputVariants({ variant: resolvedVariant, size })

  return (
    <div className={cn('w-full', label && 'space-y-2')}>
      {label && <p className="text-md text-black">{label}</p>}
      {leadingIcon ? (
        <div className={cn('flex w-full items-center gap-2', fieldClass, className)}>
          <span className="text-gray flex shrink-0 items-center">{leadingIcon}</span>
          <input ref={ref} className="placeholder:gray min-w-0 flex-1 border-0 bg-transparent p-0 outline-none disabled:cursor-not-allowed disabled:opacity-50" disabled={disabled} {...props} />
        </div>
      ) : (
        <input ref={ref} className={cn('block', fieldClass, className)} disabled={disabled} {...props} />
      )}
    </div>
  )
})

Input.displayName = 'Input'
export default Input

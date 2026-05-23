import { lazy, Suspense, useState, type ReactNode } from 'react'

const Dithering = lazy(() => import('@paper-design/shaders-react').then((mod) => ({ default: mod.Dithering })))

type LandingDitherBackgroundProps = {
  /** Accent color for the dither pattern (defaults to portal main blue). */
  accentColor?: string
  className?: string
  children?: ReactNode
}

export function LandingDitherBackground({ accentColor = '#264b82', className = '', children }: LandingDitherBackgroundProps) {
  const [isHovered, setIsHovered] = useState(false)

  return (
    <div className={`relative overflow-hidden ${className}`} onMouseEnter={() => setIsHovered(true)} onMouseLeave={() => setIsHovered(false)}>
      <Suspense fallback={<div className="bg-pale-blue/40 absolute inset-0" />}>
        <div className="pointer-events-none absolute inset-0 z-0 opacity-40 mix-blend-multiply">
          <Dithering colorBack="#00000000" colorFront={accentColor} shape="warp" type="8x8" speed={isHovered ? 0.6 : 0.2} className="size-full" minPixelRatio={1} />
        </div>
      </Suspense>

      <div className="from-pale-blue/30 pointer-events-none absolute inset-0 z-1 bg-linear-to-br via-white/80 to-white/60" />

      {children ? <div className="relative z-10">{children}</div> : null}
    </div>
  )
}

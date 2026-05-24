import { flushSync } from 'react-dom'

export function startViewTransition(update: () => void) {
  if (typeof document !== 'undefined' && 'startViewTransition' in document) {
    document.startViewTransition(() => {
      flushSync(update)
    })
    return
  }
  update()
}

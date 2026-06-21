import { useEffect, useState } from 'react'

/** Settle on a value only after it stops changing for `delayMs` — the typing
 *  pause that gates an analysis pass. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])

  return debounced
}

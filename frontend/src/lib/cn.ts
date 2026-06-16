import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Compose conditional class names and dedupe conflicting Tailwind utilities.
 * Lets a component carry its own base classes while still accepting a caller's
 * `className` override without the two fighting in the cascade.
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

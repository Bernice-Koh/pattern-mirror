import { describe, it, expect } from 'vitest'
import { wordSizeClass } from './growth-format'

describe('wordSizeClass', () => {
  it('gives the busiest word the largest step', () => {
    expect(wordSizeClass(10, 10)).toBe('text-display')
  })

  it('gives the least-flagged word the smallest step', () => {
    expect(wordSizeClass(1, 10)).toBe('text-body-sm')
  })

  it('scales a mid-range count to a middle step', () => {
    expect(wordSizeClass(5, 10)).toBe('text-subheading')
  })

  it('falls back to the smallest step when nothing has been flagged', () => {
    expect(wordSizeClass(0, 0)).toBe('text-body-sm')
  })
})

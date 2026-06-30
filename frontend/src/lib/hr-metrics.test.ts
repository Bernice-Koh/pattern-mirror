import { describe, it, expect } from 'vitest'
import {
  flagVolumeDrop,
  flagVolumeOverTime,
  overallAdoptionRate,
  shareByCategory,
  shareByDocType,
} from './hr-metrics'
import type { EffectivenessReport } from './hr-contract'

function report(over: Partial<EffectivenessReport> = {}): EffectivenessReport {
  return {
    adoption_over_time: [],
    adoption_by_category: [],
    adoption_by_doc_type: [],
    ...over,
  }
}

describe('hr-metrics', () => {
  describe('flagVolumeOverTime', () => {
    it('maps each period to its total flag count', () => {
      const result = flagVolumeOverTime(
        report({
          adoption_over_time: [
            {
              period: '2026-01',
              adopted_count: 3,
              total_count: 10,
              adoption_rate: 0.3,
            },
          ],
        }),
      )

      expect(result).toEqual([{ period: '2026-01', flag_count: 10 }])
    })
  })

  describe('flagVolumeDrop', () => {
    it('is the first-to-last fractional decline in monthly volume', () => {
      const result = flagVolumeDrop(
        report({
          adoption_over_time: [
            {
              period: '2026-01',
              adopted_count: 0,
              total_count: 100,
              adoption_rate: 0,
            },
            {
              period: '2026-02',
              adopted_count: 0,
              total_count: 66,
              adoption_rate: 0,
            },
          ],
        }),
      )

      expect(result).toBeCloseTo(0.34)
    })

    it('is null with fewer than two periods', () => {
      expect(
        flagVolumeDrop(
          report({
            adoption_over_time: [
              {
                period: '2026-01',
                adopted_count: 0,
                total_count: 10,
                adoption_rate: 0,
              },
            ],
          }),
        ),
      ).toBeNull()
    })
  })

  describe('overallAdoptionRate', () => {
    it('is firm-wide adopted over total across periods', () => {
      const result = overallAdoptionRate(
        report({
          adoption_over_time: [
            {
              period: '2026-01',
              adopted_count: 6,
              total_count: 10,
              adoption_rate: 0.6,
            },
            {
              period: '2026-02',
              adopted_count: 4,
              total_count: 10,
              adoption_rate: 0.4,
            },
          ],
        }),
      )

      expect(result).toBeCloseTo(0.5)
    })

    it('is null when there are no flags', () => {
      expect(overallAdoptionRate(report())).toBeNull()
    })
  })

  describe('shareByDocType', () => {
    it('returns each document type as a fraction of all flags', () => {
      const result = shareByDocType(
        report({
          adoption_by_doc_type: [
            {
              doc_type: 'feedback',
              adopted_count: 0,
              total_count: 30,
              adoption_rate: 0,
            },
            {
              doc_type: 'jd',
              adopted_count: 0,
              total_count: 10,
              adoption_rate: 0,
            },
          ],
        }),
      )

      expect(result).toEqual([
        { doc_type: 'feedback', share: 0.75 },
        { doc_type: 'jd', share: 0.25 },
      ])
    })
  })

  describe('shareByCategory', () => {
    it('returns categories as fractions, largest share first', () => {
      const result = shareByCategory(
        report({
          adoption_by_category: [
            {
              category: 'age',
              adopted_count: 0,
              total_count: 20,
              adoption_rate: 0,
            },
            {
              category: 'gender',
              adopted_count: 0,
              total_count: 60,
              adoption_rate: 0,
            },
          ],
        }),
      )

      expect(result).toEqual([
        { category: 'gender', share: 0.75 },
        { category: 'age', share: 0.25 },
      ])
    })
  })
})

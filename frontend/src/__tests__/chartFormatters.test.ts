import { describe, expect, it } from 'vitest'
import progressSource from '../pages/ProgressPage.tsx?raw'
import { numericTooltipFormatter } from '../chartFormatters'

/**
 * Recharts types a tooltip value as ValueType — number | string | array —
 * because a chart can plot any of those. These charts plot numbers, so four
 * call sites in ProgressPage cast their callback to `any` to force the
 * narrower signature through, each with an eslint-disable alongside (#272).
 *
 * One audited conversion replaces four unaudited ones.
 */

describe('numericTooltipFormatter', () => {
  const format = numericTooltipFormatter(v => [`${v} kg`, 'Weight'])

  it('formats a numeric value', () => {
    expect(format(42)).toEqual(['42 kg', 'Weight'])
  })

  it('accepts a numeric string, which ValueType permits', () => {
    expect(format('42')).toEqual(['42 kg', 'Weight'])
  })

  it('falls back rather than rendering NaN for a non-numeric value', () => {
    const [label] = format('n/a') as [string, string]
    expect(label).not.toContain('NaN')
  })

  it('falls back for an array value, which ValueType also permits', () => {
    const [label] = format([1, 2]) as [string, string]
    expect(label).not.toContain('NaN')
  })

  it('falls back for undefined, which Recharts passes before data arrives', () => {
    const [label] = format(undefined) as [string, string]
    expect(label).not.toContain('NaN')
  })
})

describe('ProgressPage', () => {
  it('has no `as any` casts left', () => {
    expect(progressSource).not.toMatch(/as any/)
  })

  it('has no no-explicit-any suppressions left', () => {
    expect(progressSource).not.toMatch(/no-explicit-any/)
  })
})

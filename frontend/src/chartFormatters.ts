import type { TooltipValueType } from 'recharts'

/**
 * Adapt a numeric formatter to the signature Recharts' `Tooltip` expects.
 *
 * Recharts types a tooltip value as `ValueType` — `number | string |
 * ReadonlyArray<number | string>` — because a chart can plot any of those, and
 * it may be `undefined` before data arrives. Every chart in this app plots
 * numbers, so a `(value: number) => ...` callback is rejected and four call
 * sites in ProgressPage each cast themselves to `any` to get through (#272).
 *
 * Narrowing once here replaces four unchecked casts with one conversion that
 * handles the cases the casts silently ignored: a non-numeric value used to
 * produce `NaN kg` in the tooltip rather than anything a reader could act on.
 *
 * Typed structurally rather than as Recharts' `Formatter`, which the package
 * does not export from its root — only `ValueType`, as `TooltipValueType`.
 */
export function numericTooltipFormatter(
  format: (value: number) => [string, string],
): (value: TooltipValueType | undefined) => [string, string] {
  return value => {
    const numeric = typeof value === 'number' ? value : Number(value)
    if (!Number.isFinite(numeric)) return ['—', '']
    return format(numeric)
  }
}

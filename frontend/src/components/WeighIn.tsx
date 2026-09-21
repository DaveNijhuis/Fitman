import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Scale } from 'lucide-react'
import { getFeatures } from '../api/features'
import { exchangeScale } from '../api/scale'
import type { Measurement } from '../api/measurements'
import { getBluetooth } from '../scale/bluetooth'

/**
 * Weigh in on the smart scale (#322). Only shown when the backend has the
 * scale feature on (#326); manual entry stays alongside it either way.
 *
 * The relay loads on first use, so this component is all anyone else carries.
 */
export default function WeighIn({ onMeasured }: { onMeasured: (m: Measurement) => void }) {
  const [enabled, setEnabled] = useState(false)
  const [running, setRunning] = useState(false)
  const [live, setLive] = useState<number | null>(null)
  const [result, setResult] = useState<Measurement | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    getFeatures()
      .then(f => { if (alive) setEnabled(f.scale) })
      .catch(() => {})  // no feature list, no button: manual entry still works
    return () => { alive = false }
  }, [])

  if (!enabled) return null

  const bluetooth = getBluetooth()
  if (!bluetooth) {
    return (
      <p className="text-[12px] text-[var(--color-muted)] mb-3">
        Weighing in on the smart scale needs a browser with Web Bluetooth. On iPhone, open Fitman in
        the Bluefy browser; on Android, use Chrome.
      </p>
    )
  }

  async function start(bt: NonNullable<typeof bluetooth>) {
    setRunning(true)
    setError(null)
    setResult(null)
    setLive(null)
    try {
      const { weighIn } = await import('../scale/relay')
      const m = await weighIn({
        bluetooth: bt,
        exchange: exchangeScale,
        onLiveWeight: setLive,
        utcOffsetMin: -new Date().getTimezoneOffset(),
      })
      setResult(m)
      onMeasured(m)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The weigh-in failed.')
    } finally {
      setRunning(false)
    }
  }

  const needsProfile = error?.startsWith('Complete your profile') ?? false

  return (
    <div className="mb-3 space-y-2">
      <button
        onClick={() => void start(bluetooth)}
        disabled={running}
        className="flex items-center gap-1 text-[13px] font-semibold text-[var(--color-accent)] disabled:opacity-50"
      >
        <Scale size={15} />{running ? 'Weighing in…' : 'Weigh in'}
      </button>

      {running && (
        <p className="text-[12px] text-[var(--color-muted)]">
          {live === null
            ? 'Step on barefoot and hold the handle until the scale beeps.'
            : <>Measuring… <span className="font-mono">{live.toFixed(2)} kg</span></>}
        </p>
      )}

      {result && (
        <p className="text-[12px] text-[var(--color-text)]">
          Saved: <span className="font-mono">{result.weight_kg} kg</span>
          {result.body_fat_pct != null && <> · <span className="font-mono">{result.body_fat_pct} %</span> body fat</>}
        </p>
      )}

      {error && (
        <p role="alert" className="text-[12px] text-red-500">
          {error}
          {needsProfile && <> <Link to="/settings" className="underline">Update your profile</Link></>}
        </p>
      )}
    </div>
  )
}

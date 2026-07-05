import { useEffect, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import type { Exercise } from '../api/exercises'
import type { LogEntry } from '../api/logs'

interface Props {
  session: string
  exercises: Exercise[]
  sessionLogs: Record<number, LogEntry[]>
  onConfirm: () => void
  onDiscard: () => Promise<void>
  onCancel: () => void
  loading: boolean
}

export default function FinishWorkoutSheet({ session, exercises, sessionLogs, onConfirm, onDiscard, onCancel, loading }: Props) {
  const allLogs = Object.values(sessionLogs).flat()
  const totalSets = allLogs.length
  const totalVolume = allLogs.reduce((sum, l) => sum + l.weight * l.reps, 0)
  const exercisesWorked = exercises.filter(e => (sessionLogs[e.id]?.length ?? 0) > 0).length

  const [confirmDiscard, setConfirmDiscard] = useState(false)
  const [countdown, setCountdown] = useState(0)
  const [discarding, setDiscarding] = useState(false)

  // Start countdown when discard panel opens; reset when it closes
  useEffect(() => {
    if (!confirmDiscard) { setCountdown(0); return }
    setCountdown(2)
  }, [confirmDiscard])

  // Decrement countdown each second until zero
  useEffect(() => {
    if (countdown <= 0) return
    const t = setTimeout(() => setCountdown(c => c - 1), 1000)
    return () => clearTimeout(t)
  }, [countdown])

  function dismissDiscard() { setConfirmDiscard(false) }

  async function handleDiscard() {
    setDiscarding(true)
    try {
      await onDiscard()
    } finally {
      setDiscarding(false)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-end z-50"
      onClick={confirmDiscard ? dismissDiscard : onCancel}
    >
      <div
        className="relative w-full bg-[var(--color-surface)] rounded-t-3xl px-5 pt-6 pb-10"
        onClick={e => e.stopPropagation()}
      >
        <div className="w-10 h-1 bg-[var(--color-border)] rounded-full mx-auto mb-6" />

        <h2 className="text-xl font-bold text-[var(--color-text)]">Finish {session}?</h2>

        <div className="grid grid-cols-3 gap-3 mt-5">
          <div className="bg-[var(--color-bg)] rounded-2xl p-3 text-center">
            <p className="text-2xl font-bold text-[var(--color-text)]">{exercisesWorked}</p>
            <p className="text-xs text-[var(--color-muted)] mt-0.5">Exercises</p>
          </div>
          <div className="bg-[var(--color-bg)] rounded-2xl p-3 text-center">
            <p className="text-2xl font-bold text-[var(--color-text)]">{totalSets}</p>
            <p className="text-xs text-[var(--color-muted)] mt-0.5">Sets</p>
          </div>
          <div className="bg-[var(--color-bg)] rounded-2xl p-3 text-center">
            <p className="text-2xl font-bold text-[var(--color-text)]">{totalVolume.toLocaleString()}</p>
            <p className="text-xs text-[var(--color-muted)] mt-0.5">kg volume</p>
          </div>
        </div>

        {/* Overlay — covers sheet content behind the discard panel */}
        {confirmDiscard && (
          <div
            className="absolute inset-0 z-10 rounded-t-3xl"
            onClick={dismissDiscard}
          />
        )}

        <button
          onClick={onConfirm}
          disabled={loading || discarding}
          className="mt-5 w-full py-3 bg-[var(--color-accent)] text-white font-semibold rounded-2xl disabled:opacity-50"
        >
          {loading ? 'Saving…' : 'Save & Finish'}
        </button>
        <button
          onClick={onCancel}
          disabled={loading || discarding}
          className="mt-3 w-full py-3 text-[var(--color-muted)] font-medium"
        >
          Keep going
        </button>

        {/* Discard option */}
        {!confirmDiscard ? (
          <button
            onClick={() => setConfirmDiscard(true)}
            disabled={loading || discarding}
            className="mt-2 w-full py-2 text-sm text-red-400 font-medium hover:text-red-500 transition-colors"
          >
            Discard workout
          </button>
        ) : (
          <div className="relative z-20 mt-3 p-3 rounded-2xl border border-red-200 bg-red-50 space-y-2">
            <div className="flex items-start gap-2 text-red-700">
              <AlertTriangle size={15} className="mt-0.5 shrink-0" />
              <p className="text-xs font-medium">
                All logged sets will be permanently deleted. This cannot be undone.
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={dismissDiscard}
                className="flex-1 py-2 rounded-xl border border-[var(--color-border)] text-sm font-semibold text-[var(--color-muted)]"
              >
                Cancel
              </button>
              <button
                onClick={handleDiscard}
                disabled={countdown > 0 || discarding}
                className="flex-1 py-2 rounded-xl bg-red-500 text-white text-sm font-semibold disabled:opacity-40 transition-opacity duration-300"
              >
                {discarding ? 'Discarding…' : countdown > 0 ? `Yes, discard (${countdown})` : 'Yes, discard'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

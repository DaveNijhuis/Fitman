import { useEffect, useState } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { ArrowLeft, Trash2 } from 'lucide-react'
import { deleteSession, getSessionLogs, type SessionLogEntry, type WorkoutSessionSummary } from '../api/workoutSessions'

function groupByExercise(logs: SessionLogEntry[]): Record<string, SessionLogEntry[]> {
  return logs.reduce((acc, log) => {
    const key = log.exercise_name
    acc[key] = [...(acc[key] ?? []), log]
    return acc
  }, {} as Record<string, SessionLogEntry[]>)
}

export default function WorkoutDetailPage() {
  const { sessionId } = useParams()
  const { state } = useLocation()
  const navigate = useNavigate()
  const summary = state as WorkoutSessionSummary | null

  const [logs, setLogs] = useState<SessionLogEntry[]>([])
  const [confirming, setConfirming] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  useEffect(() => {
    if (sessionId) getSessionLogs(Number(sessionId)).then(setLogs)
  }, [sessionId])

  const grouped = groupByExercise(logs)
  const date = summary ? new Date(summary.started_at).toLocaleDateString('en-GB', {
    weekday: 'long', day: 'numeric', month: 'long'
  }) : ''

  // Opened by URL there's no summary to name the workout with.
  const what = summary ? `${summary.session} from ${date}` : 'this workout'

  async function handleDelete() {
    if (!sessionId) return
    setDeleting(true)
    setDeleteError(null)
    try {
      await deleteSession(Number(sessionId))
      navigate('/history', { replace: true })
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Could not delete the workout.')
      setConfirming(false)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="min-h-screen pb-8">
      <header className="sticky top-0 bg-[var(--color-bg)] border-b border-[var(--color-border)] px-4 py-3 flex items-center gap-3">
        <button onClick={() => navigate('/history')} className="text-[var(--color-muted)]">
          <ArrowLeft size={20} />
        </button>
        <div className="flex-1">
          <h1 className="font-bold text-lg">{summary?.session}</h1>
          <p className="text-xs text-[var(--color-muted)]">{date}</p>
        </div>
        <button
          onClick={() => setConfirming(true)}
          aria-label="Delete workout"
          className="text-[var(--color-muted)] hover:text-red-500"
        >
          <Trash2 size={18} />
        </button>
      </header>

      {deleteError && (
        <p role="alert" className="mx-4 mt-3 text-sm text-red-500">{deleteError}</p>
      )}

      {confirming && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 px-4 pb-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-workout-title"
            className="w-full max-w-sm bg-[var(--color-surface)] rounded-2xl p-5 space-y-4"
          >
            <h2 id="delete-workout-title" className="font-semibold text-[var(--color-text)]">Delete workout?</h2>
            <p className="text-sm text-[var(--color-muted)]">
              Delete {what}? Its sets are removed and your records recalculate without them.
              This can't be undone.
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setConfirming(false)}
                disabled={deleting}
                className="flex-1 py-2 rounded-[10px] border border-[var(--color-border)] text-sm text-[var(--color-muted)]"
              >
                Cancel
              </button>
              <button
                onClick={() => void handleDelete()}
                disabled={deleting}
                className="flex-1 py-2 rounded-[10px] bg-red-500 text-white text-sm font-semibold disabled:opacity-50"
              >
                {deleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      <main className="px-4 pt-4 space-y-4">
        {Object.entries(grouped).map(([name, sets]) => (
          <div key={name} className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-2xl p-4">
            <p className="font-semibold text-[var(--color-text)]">{name}</p>
            <div className="mt-3 space-y-1">
              {sets.map((s, i) => (
                <div key={s.id} className="flex items-center justify-between text-sm">
                  <span className="text-[var(--color-muted)]">Set {i + 1}</span>
                  <span className="font-mono text-[var(--color-text)]">{s.weight} kg × {s.reps}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </main>
    </div>
  )
}

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Dumbbell, X } from 'lucide-react'
import { getTemplates, type Template } from '../api/templates'
import { startSession, saveActiveWorkout } from '../api/workoutSessions'

interface Props {
  onClose: () => void
}

export default function SessionPickerSheet({ onClose }: Props) {
  const navigate = useNavigate()
  const [templates, setTemplates] = useState<Template[]>([])
  const [starting, setStarting] = useState<number | null>(null)

  useEffect(() => {
    // Hidden built-ins stay off (#359); they're still in the Library.
    getTemplates().then(t => setTemplates(t.filter(x => !x.hidden))).catch(() => {})
  }, [])

  async function handleStart(template: Template) {
    setStarting(template.id)
    try {
      const workout = await startSession(template.id)
      saveActiveWorkout(workout.id, workout.session, workout.started_at)
      onClose()
      navigate(`/workout/${workout.id}`, { state: { session: workout.session, sessionId: workout.id } })
    } finally {
      setStarting(null)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-[var(--color-surface)] rounded-t-[24px] px-4 pt-5 pb-8 space-y-3">
        <div className="flex items-center justify-between mb-1">
          <h2 className="text-[17px] font-bold">Start workout</h2>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-[var(--color-bg)] flex items-center justify-center text-[var(--color-muted)]"
          >
            <X size={16} />
          </button>
        </div>
        {templates.map(template => (
          <button
            key={template.id}
            onClick={() => handleStart(template)}
            disabled={starting !== null}
            className="w-full flex items-center gap-4 p-4 bg-[var(--color-bg)] rounded-2xl border border-[var(--color-border)] hover:border-[var(--color-accent)] transition-colors disabled:opacity-50 text-left"
          >
            <div className="w-10 h-10 rounded-xl bg-[var(--color-accent-soft)] flex items-center justify-center shrink-0">
              <Dumbbell size={18} className="text-[var(--color-accent)]" />
            </div>
            <div className="flex-1">
              <p className="font-semibold text-[var(--color-text)]">{template.name}</p>
              {template.focus && (
                <p className="text-xs text-[var(--color-muted)] mt-0.5">{template.focus}</p>
              )}
            </div>
            {starting === template.id && (
              <span className="text-sm text-[var(--color-muted)] shrink-0">Starting…</span>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}

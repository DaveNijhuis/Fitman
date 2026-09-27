import { useId, useState } from 'react'
import { X } from 'lucide-react'
import {
  createExercise, updateExercise, deleteExercise, type Exercise, type ExerciseIn,
} from '../api/exercises'

interface Props {
  /** The exercise to edit; none to add a new one. */
  exercise?: Exercise | undefined
  /** Equipment already in the library, offered as suggestions. */
  equipment: string[]
  onClose: () => void
  /** After a save or delete, so the library can refresh. */
  onChanged: () => void
}

const FIELD = 'w-full px-3 py-2.5 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]'

/** Add or edit a custom exercise, with any equipment (#358). */
export default function ExerciseFormSheet({ exercise, equipment, onClose, onChanged }: Props) {
  const id = useId()
  const [name, setName] = useState(exercise?.name ?? '')
  const [muscles, setMuscles] = useState(exercise?.muscles ?? '')
  const [type, setType] = useState<ExerciseIn['type']>(exercise?.type === 'bodyweight' ? 'bodyweight' : 'weight')
  const [equip, setEquip] = useState(exercise?.equip ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)

  async function run(action: () => Promise<unknown>) {
    setSaving(true)
    setError(null)
    try {
      await action()
      onChanged()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
      setConfirming(false)
    } finally {
      setSaving(false)
    }
  }

  function save() {
    const body: ExerciseIn = { name: name.trim(), muscles: muscles.trim() || null, type, equip: equip.trim() }
    void run(() => (exercise ? updateExercise(exercise.id, body) : createExercise(body)))
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${id}-title`}
        className="relative bg-[var(--color-surface)] rounded-t-[24px] px-4 pt-5 pb-8 space-y-4"
      >
        <div className="flex items-center justify-between">
          <h2 id={`${id}-title`} className="text-[17px] font-bold">
            {exercise ? 'Edit exercise' : 'Add exercise'}
          </h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="w-8 h-8 rounded-full bg-[var(--color-bg)] flex items-center justify-center text-[var(--color-muted)]"
          >
            <X size={16} />
          </button>
        </div>

        <form
          className="space-y-3"
          onSubmit={e => { e.preventDefault(); save() }}
        >
          <label className="block space-y-1">
            <span className="text-xs font-medium text-[var(--color-muted)]">Name</span>
            <input className={FIELD} value={name} onChange={e => setName(e.target.value)} required />
          </label>

          <label className="block space-y-1">
            <span className="text-xs font-medium text-[var(--color-muted)]">Muscles</span>
            <input
              className={FIELD}
              value={muscles}
              onChange={e => setMuscles(e.target.value)}
              placeholder="e.g. Chest, Front Delt"
            />
          </label>

          <fieldset className="space-y-1">
            <legend className="text-xs font-medium text-[var(--color-muted)]">Type</legend>
            <div className="flex gap-2">
              {(['weight', 'bodyweight'] as const).map(t => (
                <label
                  key={t}
                  className={`flex-1 text-center py-2 rounded-xl border text-sm cursor-pointer ${
                    type === t
                      ? 'border-[var(--color-accent)] text-[var(--color-accent)] font-semibold'
                      : 'border-[var(--color-border)] text-[var(--color-muted)]'
                  }`}
                >
                  <input
                    type="radio"
                    name={`${id}-type`}
                    value={t}
                    checked={type === t}
                    onChange={() => setType(t)}
                    className="sr-only"
                  />
                  {t === 'weight' ? 'Weight' : 'Bodyweight'}
                </label>
              ))}
            </div>
          </fieldset>

          <label className="block space-y-1">
            <span className="text-xs font-medium text-[var(--color-muted)]">Equipment</span>
            <input
              className={FIELD}
              value={equip}
              onChange={e => setEquip(e.target.value)}
              list={`${id}-equipment`}
              placeholder="Dumbbell, Cable, Machine…"
              required
            />
            <datalist id={`${id}-equipment`}>
              {equipment.map(e => <option key={e} value={e} />)}
            </datalist>
          </label>

          {error && <p role="alert" className="text-sm text-red-500">{error}</p>}

          <div className="flex gap-2 pt-1">
            {exercise && (
              <button
                type="button"
                onClick={() => setConfirming(true)}
                disabled={saving}
                className="px-4 py-2.5 rounded-xl border border-[var(--color-border)] text-sm text-red-500 disabled:opacity-50"
              >
                Delete
              </button>
            )}
            <button
              type="submit"
              disabled={saving}
              className="flex-1 py-2.5 rounded-xl bg-[var(--color-accent)] text-white text-sm font-semibold disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>

        {confirming && exercise && (
          <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 px-4 pb-4">
            <div
              role="alertdialog"
              aria-modal="true"
              aria-labelledby={`${id}-delete-title`}
              className="w-full max-w-sm bg-[var(--color-surface)] rounded-2xl p-5 space-y-4"
            >
              <h2 id={`${id}-delete-title`} className="font-semibold text-[var(--color-text)]">Delete exercise?</h2>
              <p className="text-sm text-[var(--color-muted)]">
                Delete {exercise.name}? If you've logged sets with it, it's archived instead:
                hidden from the library, with its history, charts and records kept.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setConfirming(false)}
                  disabled={saving}
                  className="flex-1 py-2 rounded-[10px] border border-[var(--color-border)] text-sm text-[var(--color-muted)]"
                >
                  Cancel
                </button>
                <button
                  onClick={() => void run(() => deleteExercise(exercise.id))}
                  disabled={saving}
                  className="flex-1 py-2 rounded-[10px] bg-red-500 text-white text-sm font-semibold disabled:opacity-50"
                >
                  {saving ? 'Deleting…' : 'Delete'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

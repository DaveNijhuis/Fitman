import { useEffect, useId, useState } from 'react'
import { X, ChevronUp, ChevronDown, Plus, Minus } from 'lucide-react'
import { getAllExercises, type Exercise } from '../api/exercises'
import {
  createTemplate, updateTemplate, deleteTemplate, getTemplate, type Template, type TemplateIn,
} from '../api/templates'

interface Props {
  /** The user's own day to edit; none to build a new one. */
  template?: Template | undefined
  onClose: () => void
  /** After a save or delete, so the list can refresh. */
  onChanged: () => void
}

/** Colours to pick from: the built-in categories' first (#357), then three more. */
const COLOURS = [
  { name: 'Orange', value: '#ff5a36' },
  { name: 'Blue', value: '#3b82f6' },
  { name: 'Green', value: '#1f9d62' },
  { name: 'Amber', value: '#f59e0b' },
  { name: 'Violet', value: '#8b5cf6' },
  { name: 'Teal', value: '#14b8a6' },
]

const FIELD = 'w-full px-3 py-2.5 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]'
const ICON_BUTTON = 'w-7 h-7 rounded-lg flex items-center justify-center text-[var(--color-muted)] hover:bg-[var(--color-bg)] disabled:opacity-30'

/** Build or edit your own day from the library (#359). */
export default function TemplateFormSheet({ template, onClose, onChanged }: Props) {
  const id = useId()
  const [name, setName] = useState(template?.name ?? '')
  const [focus, setFocus] = useState(template?.focus ?? '')
  const [colour, setColour] = useState(template?.colour ?? COLOURS[0]!.value)
  const [chosen, setChosen] = useState<Exercise[]>([])
  const [library, setLibrary] = useState<Exercise[]>([])
  const [find, setFind] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirming, setConfirming] = useState(false)

  useEffect(() => {
    getAllExercises().then(setLibrary).catch(() => {})
    if (template) getTemplate(template.id).then(t => setChosen(t.exercises)).catch(() => {})
  }, [template])

  const chosenIds = new Set(chosen.map(e => e.id))
  const available = library.filter(
    e => !chosenIds.has(e.id) && e.name.toLowerCase().includes(find.trim().toLowerCase()),
  )

  function move(index: number, by: -1 | 1) {
    setChosen(list => {
      const next = [...list]
      const [item] = next.splice(index, 1)
      next.splice(index + by, 0, item!)
      return next
    })
  }

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
    const body: TemplateIn = {
      name: name.trim(),
      focus: focus.trim() || null,
      colour,
      exercise_ids: chosen.map(e => e.id),
    }
    void run(() => (template ? updateTemplate(template.id, body) : createTemplate(body)))
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${id}-title`}
        className="relative bg-[var(--color-surface)] rounded-t-[24px] px-4 pt-5 pb-8 space-y-4 max-h-[90vh] overflow-y-auto"
      >
        <div className="flex items-center justify-between">
          <h2 id={`${id}-title`} className="text-[17px] font-bold">
            {template ? 'Edit day' : 'New day'}
          </h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="w-8 h-8 rounded-full bg-[var(--color-bg)] flex items-center justify-center text-[var(--color-muted)]"
          >
            <X size={16} />
          </button>
        </div>

        <form className="space-y-3" onSubmit={e => { e.preventDefault(); save() }}>
          <label className="block space-y-1">
            <span className="text-xs font-medium text-[var(--color-muted)]">Name</span>
            <input className={FIELD} value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Chest Day" required />
          </label>

          <label className="block space-y-1">
            <span className="text-xs font-medium text-[var(--color-muted)]">Focus</span>
            <input className={FIELD} value={focus} onChange={e => setFocus(e.target.value)} placeholder="e.g. Chest · Triceps" />
          </label>

          <fieldset className="space-y-1">
            <legend className="text-xs font-medium text-[var(--color-muted)]">Colour</legend>
            <div className="flex gap-2">
              {COLOURS.map(c => (
                <label key={c.value} className="cursor-pointer" title={c.name}>
                  <input
                    type="radio"
                    name={`${id}-colour`}
                    value={c.value}
                    checked={colour === c.value}
                    onChange={() => setColour(c.value)}
                    aria-label={c.name}
                    className="sr-only peer"
                  />
                  <span
                    className="block w-7 h-7 rounded-full ring-offset-2 ring-offset-[var(--color-surface)] peer-checked:ring-2 peer-checked:ring-[var(--color-text)]"
                    style={{ background: c.value }}
                  />
                </label>
              ))}
            </div>
          </fieldset>

          <div className="space-y-1">
            <p className="text-xs font-medium text-[var(--color-muted)]">Exercises, in order</p>
            {chosen.length === 0 ? (
              <p className="text-sm text-[var(--color-muted)] py-2">Add exercises from the library below.</p>
            ) : (
              <ol className="space-y-1">
                {chosen.map((e, i) => (
                  <li key={e.id} className="flex items-center gap-1 px-3 py-2 rounded-xl bg-[var(--color-bg)]">
                    <span className="flex-1 text-sm truncate">{e.name}</span>
                    <button type="button" className={ICON_BUTTON} aria-label={`Move ${e.name} up`} disabled={i === 0} onClick={() => move(i, -1)}>
                      <ChevronUp size={16} />
                    </button>
                    <button type="button" className={ICON_BUTTON} aria-label={`Move ${e.name} down`} disabled={i === chosen.length - 1} onClick={() => move(i, 1)}>
                      <ChevronDown size={16} />
                    </button>
                    <button type="button" className={ICON_BUTTON} aria-label={`Remove ${e.name}`} onClick={() => setChosen(list => list.filter(x => x.id !== e.id))}>
                      <Minus size={16} />
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </div>

          <div className="space-y-1">
            <input
              className={FIELD}
              value={find}
              onChange={e => setFind(e.target.value)}
              placeholder="Find exercises…"
              aria-label="Find exercises"
            />
            <ul className="max-h-48 overflow-y-auto divide-y divide-[var(--color-border)]">
              {available.map(e => (
                <li key={e.id}>
                  <button
                    type="button"
                    aria-label={`Add ${e.name}`}
                    onClick={() => setChosen(list => [...list, e])}
                    className="w-full flex items-center gap-2 px-1 py-2 text-left hover:bg-[var(--color-bg)]"
                  >
                    <Plus size={14} className="text-[var(--color-accent)] shrink-0" />
                    <span className="flex-1 text-sm truncate">{e.name}</span>
                    <span className="text-[10px] text-[var(--color-muted)]">{e.equip}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {error && <p role="alert" className="text-sm text-red-500">{error}</p>}

          <div className="flex gap-2 pt-1">
            {template && (
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
              disabled={saving || !name.trim() || chosen.length === 0}
              className="flex-1 py-2.5 rounded-xl bg-[var(--color-accent)] text-white text-sm font-semibold disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>

        {confirming && template && (
          <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 px-4 pb-4">
            <div
              role="alertdialog"
              aria-modal="true"
              aria-labelledby={`${id}-delete-title`}
              className="w-full max-w-sm bg-[var(--color-surface)] rounded-2xl p-5 space-y-4"
            >
              <h2 id={`${id}-delete-title`} className="font-semibold text-[var(--color-text)]">Delete day?</h2>
              <p className="text-sm text-[var(--color-muted)]">
                Delete {template.name}? Your past workouts from it stay in History, with their sets and records.
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
                  onClick={() => void run(() => deleteTemplate(template.id))}
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

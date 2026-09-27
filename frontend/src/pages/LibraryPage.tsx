import { useEffect, useState } from 'react'
import { Search, Plus, Pencil, Copy, Eye, EyeOff } from 'lucide-react'
import { getAllExercises, getEquipment, type Exercise } from '../api/exercises'
import { getTemplates, duplicateTemplate, setTemplateHidden, type Template } from '../api/templates'
import ExerciseFormSheet from '../components/ExerciseFormSheet'
import TemplateFormSheet from '../components/TemplateFormSheet'

const EQUIP_COLORS: Record<string, string> = {
  Dumbbell:   'bg-blue-50 text-blue-700',
  Bodyweight: 'bg-green-50 text-green-700',
}

export default function LibraryPage() {
  const [exercises, setExercises] = useState<Exercise[]>([])
  const [templates, setTemplates] = useState<Template[]>([])
  // null is All: the whole library.
  const [activeTemplate, setActiveTemplate] = useState<number | null>(null)
  const [equipment, setEquipment] = useState<string[]>([])
  // null is any equipment.
  const [activeEquip, setActiveEquip] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  // The form sheet: 'new' to add, an exercise to edit, null when closed (#358).
  const [editing, setEditing] = useState<Exercise | 'new' | null>(null)
  // Bumped after a save or delete, to fetch the library again.
  const [version, setVersion] = useState(0)
  // The day sheet: 'new' to build one, your own day to edit, null when closed (#359).
  const [editingDay, setEditingDay] = useState<Template | 'new' | null>(null)
  // Bumped after a day changes, to fetch the days again.
  const [daysVersion, setDaysVersion] = useState(0)
  const [dayError, setDayError] = useState<string | null>(null)

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => {
    getTemplates().then(setTemplates).catch(() => {})
  }, [daysVersion])

  async function dayAction(action: () => Promise<unknown>) {
    setDayError(null)
    try {
      await action()
      setDaysVersion(v => v + 1)
    } catch (err) {
      setDayError(err instanceof Error ? err.message : 'Something went wrong.')
    }
  }

  useEffect(() => {
    getEquipment().then(setEquipment).catch(() => {})
  }, [version])

  useEffect(() => {
    getAllExercises(activeTemplate ?? undefined, debouncedSearch || undefined, activeEquip ?? undefined)
      .then(setExercises)
      .catch(() => {})  // keep what's shown; the next change of filter tries again
  }, [activeTemplate, debouncedSearch, activeEquip, version])

  const tabs: { id: number | null; label: string }[] = [
    { id: null, label: 'All' },
    ...templates.map(t => ({ id: t.id, label: t.name })),
  ]

  return (
    <div className="min-h-screen pb-6">
      <header className="px-4 pt-12 pb-4">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold tracking-tight">Library</h1>
          <button
            onClick={() => setEditing('new')}
            aria-label="Add exercise"
            className="w-9 h-9 rounded-full bg-[var(--color-accent)] text-white flex items-center justify-center"
          >
            <Plus size={18} />
          </button>
        </div>

        {/* Search */}
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-muted)]" />
          <input
            type="text"
            placeholder="Search exercises…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]"
          />
        </div>
      </header>

      {/* My days: built-ins to duplicate or hide, your own to edit (#359) */}
      <section className="mx-4 mb-4 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-2xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
          <h2 className="font-semibold text-[var(--color-text)]">My days</h2>
          <button
            onClick={() => setEditingDay('new')}
            className="flex items-center gap-1 text-xs font-semibold text-[var(--color-accent)]"
          >
            <Plus size={14} /> New day
          </button>
        </div>
        {dayError && <p role="alert" className="px-4 pt-2 text-sm text-red-500">{dayError}</p>}
        <ul className="divide-y divide-[var(--color-border)]">
          {templates.map(t => (
            <li key={t.id} className={`flex items-center gap-3 px-4 py-2.5 ${t.hidden ? 'opacity-50' : ''}`}>
              <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: t.colour ?? 'var(--color-accent)' }} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[var(--color-text)] truncate">{t.name}</p>
                {t.focus && <p className="text-xs text-[var(--color-muted)] truncate">{t.focus}</p>}
              </div>
              {t.builtin ? (
                <>
                  <button
                    onClick={() => void dayAction(() => duplicateTemplate(t.id))}
                    aria-label={`Duplicate ${t.name}`}
                    className="text-[var(--color-muted)] hover:text-[var(--color-text)]"
                  >
                    <Copy size={15} />
                  </button>
                  <button
                    onClick={() => void dayAction(() => setTemplateHidden(t.id, !t.hidden))}
                    aria-label={`${t.hidden ? 'Show' : 'Hide'} ${t.name}`}
                    className="text-[var(--color-muted)] hover:text-[var(--color-text)]"
                  >
                    {t.hidden ? <EyeOff size={15} /> : <Eye size={15} />}
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setEditingDay(t)}
                  aria-label={`Edit ${t.name}`}
                  className="text-[var(--color-muted)] hover:text-[var(--color-text)]"
                >
                  <Pencil size={15} />
                </button>
              )}
            </li>
          ))}
        </ul>
      </section>

      {/* Template tabs */}
      <div className="flex gap-2 px-4 pb-4 overflow-x-auto no-scrollbar">
        {tabs.map(tab => (
          <button
            key={tab.id ?? 'all'}
            onClick={() => setActiveTemplate(tab.id)}
            className={`px-3 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
              activeTemplate === tab.id
                ? 'bg-[var(--color-accent)] text-white'
                : 'bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-muted)]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Equipment: whatever is in the library, built-in or the user's own (#358) */}
      {equipment.length > 0 && (
        <div className="flex gap-2 px-4 pb-4 overflow-x-auto no-scrollbar">
          {[null, ...equipment].map(e => (
            <button
              key={e ?? 'any'}
              onClick={() => setActiveEquip(e)}
              className={`px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-colors ${
                activeEquip === e
                  ? 'bg-[var(--color-text)] text-[var(--color-surface)]'
                  : 'bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-muted)]'
              }`}
            >
              {e ?? 'All equipment'}
            </button>
          ))}
        </div>
      )}

      <main className="px-4">
        {exercises.length === 0 ? (
          <p className="text-sm text-[var(--color-muted)] text-center mt-12">No exercises found.</p>
        ) : (
          <div className="space-y-2">
            {exercises.map(ex => (
              <div
                key={ex.id}
                className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] px-4 py-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-[var(--color-text)] truncate">{ex.name}</p>
                    {ex.muscles && (
                      <p className="text-xs text-[var(--color-muted)] mt-0.5">{ex.muscles}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${EQUIP_COLORS[ex.equip] ?? 'bg-gray-100 text-gray-600'}`}>
                      {ex.equip}
                    </span>
                    {ex.custom && (
                      <button
                        onClick={() => setEditing(ex)}
                        aria-label={`Edit ${ex.name}`}
                        className="text-[var(--color-muted)] hover:text-[var(--color-text)]"
                      >
                        <Pencil size={14} />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {editingDay && (
        <TemplateFormSheet
          template={editingDay === 'new' ? undefined : editingDay}
          onClose={() => setEditingDay(null)}
          onChanged={() => setDaysVersion(v => v + 1)}
        />
      )}

      {editing && (
        <ExerciseFormSheet
          exercise={editing === 'new' ? undefined : editing}
          equipment={equipment}
          onClose={() => setEditing(null)}
          onChanged={() => setVersion(v => v + 1)}
        />
      )}
    </div>
  )
}

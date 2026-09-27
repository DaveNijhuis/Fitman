import { useEffect, useState } from 'react'
import { Search, Plus, Pencil } from 'lucide-react'
import { getAllExercises, getEquipment, type Exercise } from '../api/exercises'
import { getTemplates, type Template } from '../api/templates'
import ExerciseFormSheet from '../components/ExerciseFormSheet'

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

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => {
    getTemplates().then(setTemplates).catch(() => {})
  }, [])

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

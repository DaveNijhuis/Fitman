import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { getAllExercises, type Exercise } from '../api/exercises'
import { getTemplates, type Template } from '../api/templates'

const EQUIP_COLORS: Record<string, string> = {
  Dumbbell:   'bg-blue-50 text-blue-700',
  Bodyweight: 'bg-green-50 text-green-700',
}

export default function LibraryPage() {
  const [exercises, setExercises] = useState<Exercise[]>([])
  const [templates, setTemplates] = useState<Template[]>([])
  // null is All: the whole library.
  const [activeTemplate, setActiveTemplate] = useState<number | null>(null)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => {
    getTemplates().then(setTemplates).catch(() => {})
  }, [])

  useEffect(() => {
    getAllExercises(activeTemplate ?? undefined, debouncedSearch || undefined).then(setExercises)
  }, [activeTemplate, debouncedSearch])

  const tabs: { id: number | null; label: string }[] = [
    { id: null, label: 'All' },
    ...templates.map(t => ({ id: t.id, label: t.name })),
  ]

  return (
    <div className="min-h-screen pb-6">
      <header className="px-4 pt-12 pb-4">
        <h1 className="text-2xl font-bold tracking-tight mb-4">Library</h1>

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
                  <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full shrink-0 ${EQUIP_COLORS[ex.equip] ?? 'bg-gray-100 text-gray-600'}`}>
                    {ex.equip}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

    </div>
  )
}

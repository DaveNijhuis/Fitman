import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { Plus, Check, Clock, Dumbbell } from 'lucide-react'
import { getExercises, type Exercise } from '../api/exercises'
import { getLastSet, logSet, type LogEntry } from '../api/logs'
import { endSession, discardSession, clearActiveWorkout, getActiveWorkout, getSessionLogs, type SessionLogEntry } from '../api/workoutSessions'
import FinishWorkoutSheet from '../components/FinishWorkoutSheet'

interface SetRow {
  weight: string
  reps: string
  done: boolean
  logEntry: LogEntry | null
}

function fmtClock(s: number): string {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m}:${String(sec).padStart(2, '0')}`
}

function fmtVol(kg: number): string {
  return kg >= 1000 ? `${(kg / 1000).toFixed(1).replace(/\.0$/, '')}k` : String(Math.round(kg))
}

function Stepper({ value, onChange, step }: { value: string; onChange: (v: string) => void; step: number }) {
  const num = parseFloat(value) || 0
  return (
    <div className="flex items-center bg-[var(--color-bg)] rounded-[9px] overflow-hidden w-full">
      <button
        onClick={() => onChange(String(Math.max(0, +(num - step).toFixed(2))))}
        className="w-7 h-[34px] text-[var(--color-muted)] text-base font-semibold hover:text-[var(--color-accent)] shrink-0"
      >−</button>
      <input
        type="text"
        inputMode="decimal"
        value={value}
        onChange={e => onChange(e.target.value)}
        onFocus={e => e.currentTarget.select()}
        className="min-w-0 w-full text-center bg-transparent border-none font-mono text-[15px] font-medium text-[var(--color-text)] py-2 focus:outline-none"
        style={{ MozAppearance: 'textfield' } as React.CSSProperties}
      />
      <button
        onClick={() => onChange(String(+(num + step).toFixed(2)))}
        className="w-7 h-[34px] text-[var(--color-muted)] text-base font-semibold hover:text-[var(--color-accent)] shrink-0"
      >+</button>
    </div>
  )
}

export default function ActiveWorkoutPage() {
  const { sessionId } = useParams()
  const { state } = useLocation()
  const navigate = useNavigate()

  const session: string = state?.session ?? ''
  const id = Number(sessionId)

  const startedAt = useRef(
    (() => {
      const saved = getActiveWorkout()
      return saved?.startedAt ? new Date(saved.startedAt).getTime() : Date.now()
    })()
  )
  const [elapsed, setElapsed] = useState(0)
  const [exercises, setExercises] = useState<Exercise[]>([])
  const [lastSets, setLastSets] = useState<Record<number, LogEntry | null>>({})
  const [sets, setSets] = useState<Record<number, SetRow[]>>({})
  const [rest, setRest] = useState(0)
  const [exercisesLoading, setExercisesLoading] = useState(true)
  const [setLogError, setSetLogError] = useState<string | null>(null)
  const [showSummary, setShowSummary] = useState(false)
  const [finishing, setFinishing] = useState(false)

  // Elapsed timer
  useEffect(() => {
    const tick = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt.current) / 1000))
    }, 1000)
    return () => clearInterval(tick)
  }, [])

  // Rest countdown
  useEffect(() => {
    if (rest <= 0) return
    const tick = setInterval(() => setRest(r => (r <= 1 ? 0 : r - 1)), 1000)
    return () => clearInterval(tick)
  }, [rest > 0])

  // Load exercises, previous sets, and any already-completed sets for this session
  useEffect(() => {
    if (!session) { navigate('/'); return }
    Promise.all([getExercises(session), getSessionLogs(id)])
      .then(([exs, currentLogs]) => {
        setExercises(exs)

        const logsByExercise: Record<number, SessionLogEntry[]> = {}
        for (const log of currentLogs) {
          ;(logsByExercise[log.exercise_id] ??= []).push(log)
        }

        return Promise.all(exs.map(e => getLastSet(e.id))).then(results => {
          const lastMap: Record<number, LogEntry | null> = {}
          const setsMap: Record<number, SetRow[]> = {}
          exs.forEach((e, i) => {
            const last = results[i]
            lastMap[e.id] = last

            const doneLogs = logsByExercise[e.id] ?? []
            const doneRows: SetRow[] = doneLogs.map(log => ({
              weight: String(log.weight),
              reps: String(log.reps),
              done: true,
              logEntry: log as unknown as LogEntry,
            }))

            const lastDone = doneLogs[doneLogs.length - 1]
            const prefill = lastDone
              ? { weight: String(lastDone.weight), reps: String(lastDone.reps) }
              : { weight: last ? String(last.weight) : '', reps: last ? String(last.reps) : '' }

            const emptyCount = Math.max(3, doneLogs.length + 1) - doneRows.length
            const emptyRows: SetRow[] = Array.from({ length: emptyCount }, () => ({
              ...prefill, done: false, logEntry: null,
            }))

            setsMap[e.id] = [...doneRows, ...emptyRows]
          })
          setLastSets(lastMap)
          setSets(setsMap)
        })
      })
      .catch(() => {})
      .finally(() => setExercisesLoading(false))
  }, [session])

  function updateSet(exerciseId: number, si: number, field: 'weight' | 'reps', value: string) {
    setSets(prev => {
      const exSets = [...(prev[exerciseId] ?? [])]
      exSets[si] = { ...exSets[si], [field]: value }
      return { ...prev, [exerciseId]: exSets }
    })
  }

  async function toggleSet(exerciseId: number, si: number) {
    const row = sets[exerciseId]?.[si]
    if (!row || row.done) return
    const weight = parseFloat(row.weight)
    const reps = parseInt(row.reps, 10)
    if (isNaN(reps) || reps <= 0) return
    try {
      const logEntry = await logSet(exerciseId, id, isNaN(weight) ? 0 : weight, reps)
      setSets(prev => {
        const exSets = [...(prev[exerciseId] ?? [])]
        exSets[si] = { ...exSets[si], done: true, logEntry }
        return { ...prev, [exerciseId]: exSets }
      })
      setRest(90)
    } catch {
      setSetLogError('Set not saved — please retry.')
      setTimeout(() => setSetLogError(null), 4000)
    }
  }

  function addSet(exerciseId: number) {
    setSets(prev => {
      const exSets = prev[exerciseId] ?? []
      const last = exSets[exSets.length - 1] ?? { weight: '', reps: '' }
      return {
        ...prev,
        [exerciseId]: [...exSets, { weight: last.weight, reps: last.reps, done: false, logEntry: null }],
      }
    })
  }

  // Header stats
  const allSets = Object.values(sets).flat()
  const doneCount = allSets.filter(s => s.done).length
  const totalCount = allSets.length
  const volume = allSets
    .filter(s => s.done)
    .reduce((sum, s) => sum + (parseFloat(s.weight) || 0) * (parseInt(s.reps, 10) || 0), 0)

  // Build sessionLogs for FinishWorkoutSheet
  const sessionLogs: Record<number, LogEntry[]> = {}
  for (const ex of exercises) {
    const done = (sets[ex.id] ?? []).filter(s => s.done && s.logEntry).map(s => s.logEntry!)
    if (done.length > 0) sessionLogs[ex.id] = done
  }

  async function handleConfirmFinish() {
    setFinishing(true)
    try {
      await endSession(id)
      clearActiveWorkout()
      navigate('/')
    } finally {
      setFinishing(false)
    }
  }

  async function handleDiscard() {
    await discardSession(id)
    clearActiveWorkout()
    navigate('/')
  }

  return (
    <div className="pb-10">

      {/* Dark sticky header */}
      <div className="sticky top-0 z-[14] bg-[var(--color-text)] text-white px-[18px] pt-[52px] pb-[14px] rounded-b-[22px] md:pt-5 md:rounded-none">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="text-[12.5px] font-bold uppercase tracking-[0.04em] truncate" style={{ color: 'rgba(255,255,255,.55)' }}>
              {session}
            </div>
            <div className="font-mono text-[32px] font-medium leading-none tracking-[0.02em] mt-0.5">
              {fmtClock(elapsed)}
            </div>
            <div className="text-[12.5px] font-semibold mt-1" style={{ color: 'rgba(255,255,255,.6)' }}>
              {fmtVol(volume)} kg · {doneCount}/{totalCount} sets
            </div>
          </div>
          <button
            onClick={() => setShowSummary(true)}
            className="bg-white text-[var(--color-text)] font-bold text-[15px] px-[18px] py-[11px] rounded-[14px] shrink-0 mt-1"
          >
            Finish
          </button>
        </div>
        {/* Progress bar */}
        <div className="mt-[14px] h-[7px] rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,.18)' }}>
          <div
            className="h-full bg-white rounded-full transition-[width] duration-[400ms] ease-out"
            style={{ width: `${totalCount > 0 ? (doneCount / totalCount) * 100 : 0}%` }}
          />
        </div>
      </div>

      <div className="px-4 pt-[14px]">

        {/* Rest timer */}
        {rest > 0 && (
          <div className="fm-fadein flex items-center justify-between bg-[var(--color-accent)] text-white px-4 py-3 rounded-[14px] mb-4">
            <div className="flex items-center gap-[10px]">
              <Clock size={20} strokeWidth={2} />
              <div>
                <div className="font-mono text-[15px] font-bold leading-none">{fmtClock(rest)}</div>
                <div className="text-[11.5px] font-semibold opacity-85 mt-0.5 whitespace-nowrap">Rest timer</div>
              </div>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setRest(r => r + 15)}
                className="font-bold text-[13px] px-3 py-2 rounded-[10px]"
                style={{ background: 'rgba(255,255,255,.22)' }}
              >+15s</button>
              <button
                onClick={() => setRest(0)}
                className="bg-white text-[var(--color-accent)] font-bold text-[13px] px-[14px] py-2 rounded-[10px]"
              >Skip</button>
            </div>
          </div>
        )}

        {setLogError && (
          <div className="flex items-center gap-3 px-4 py-3 rounded-[14px] bg-red-50 border border-red-200 text-red-600 text-sm font-semibold">
            {setLogError}
          </div>
        )}

        {/* Exercise cards — 2-col on desktop */}
        {exercisesLoading ? (
          <div className="flex items-center justify-center py-16 text-sm text-[var(--color-muted)] font-semibold">
            Loading exercises…
          </div>
        ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-[14px]">
          {exercises.map(ex => {
            const exSets = sets[ex.id] ?? []
            const exDone = exSets.filter(s => s.done).length
            const prev = lastSets[ex.id]

            return (
              <div
                key={ex.id}
                className="bg-[var(--color-surface)] rounded-[22px] overflow-hidden"
                style={{ boxShadow: '0 1px 2px rgba(40,34,24,.04), 0 8px 24px rgba(40,34,24,.05)' }}
              >
                {/* Exercise header */}
                <div className="flex items-center gap-3 px-4 pt-[15px] pb-3">
                  <div className="w-10 h-10 rounded-[11px] bg-[var(--color-accent-soft)] text-[var(--color-accent)] flex items-center justify-center shrink-0">
                    <Dumbbell size={20} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-bold text-[15px] text-[var(--color-text)] truncate">{ex.name}</div>
                    <div className="text-[11.5px] text-[var(--color-muted)] font-semibold mt-0.5">
                      {[ex.muscles, ex.equip].filter(Boolean).join(' · ')}
                    </div>
                  </div>
                  <div className={`font-mono text-[12.5px] font-semibold ${exDone === exSets.length && exSets.length > 0 ? 'text-[var(--color-good)]' : 'text-[var(--color-muted)]'}`}>
                    {exDone}/{exSets.length}
                  </div>
                </div>

                {/* Column headers */}
                <div
                  className="px-4 py-1 text-[10.5px] font-bold uppercase tracking-[0.05em] text-[var(--color-faint)]"
                  style={{ display: 'grid', gridTemplateColumns: '34px 1fr 1fr 1fr 44px', gap: 6 }}
                >
                  <span className="text-center">Set</span>
                  <span className="text-center">Prev</span>
                  <span className="text-center">Kg</span>
                  <span className="text-center">Reps</span>
                  <span />
                </div>

                {/* Set rows */}
                {exSets.map((row, si) => (
                  <div
                    key={si}
                    className="px-4 py-[7px] border-t border-[var(--color-border)]"
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '34px 1fr 1fr 1fr 44px',
                      gap: 6,
                      alignItems: 'center',
                      background: row.done ? 'var(--color-good-soft)' : undefined,
                    }}
                  >
                    {/* Set number / checkmark */}
                    <div className="flex justify-center">
                      <div className={`w-[26px] h-[26px] rounded-[8px] flex items-center justify-center font-bold text-[12.5px] font-mono ${
                        row.done ? 'bg-[var(--color-good)] text-white' : 'bg-[var(--color-bg)] text-[var(--color-muted)]'
                      }`}>
                        {row.done ? <Check size={15} strokeWidth={2.6} /> : si + 1}
                      </div>
                    </div>

                    {/* Prev */}
                    <div className="text-center font-mono text-[13px] font-semibold text-[var(--color-faint)]">
                      {prev ? `${prev.weight}×${prev.reps}` : '–'}
                    </div>

                    {/* Weight stepper */}
                    <Stepper value={row.weight} onChange={v => updateSet(ex.id, si, 'weight', v)} step={2.5} />

                    {/* Reps stepper */}
                    <Stepper value={row.reps} onChange={v => updateSet(ex.id, si, 'reps', v)} step={1} />

                    {/* Check button */}
                    <div className="flex justify-center">
                      <button
                        onClick={() => toggleSet(ex.id, si)}
                        disabled={row.done}
                        className={`w-[34px] h-[34px] rounded-[9px] flex items-center justify-center transition-all duration-[140ms] ${
                          row.done
                            ? 'bg-[var(--color-good)]'
                            : 'bg-[var(--color-surface)] border-[1.6px] border-[var(--color-border-strong)]'
                        }`}
                      >
                        <Check size={19} strokeWidth={2.6} color={row.done ? '#fff' : 'var(--color-border-strong)'} />
                      </button>
                    </div>
                  </div>
                ))}

                {/* Add set */}
                <button
                  onClick={() => addSet(ex.id)}
                  className="w-full py-[11px] font-bold text-[13.5px] text-[var(--color-accent)] border-t border-[var(--color-border)] flex items-center justify-center gap-1.5 hover:bg-[var(--color-accent-soft)] transition-colors"
                >
                  <Plus size={15} strokeWidth={2.2} /> Add set
                </button>
              </div>
            )
          })}
        </div>
        )}

        {/* Bottom finish button */}
        <button
          onClick={() => setShowSummary(true)}
          className="mt-6 w-full py-4 bg-[var(--color-accent)] text-white font-bold text-[16px] rounded-[14px] flex items-center justify-center gap-2"
        >
          <Check size={19} strokeWidth={2.4} /> Finish workout
        </button>

      </div>

      {showSummary && (
        <FinishWorkoutSheet
          session={session}
          exercises={exercises}
          sessionLogs={sessionLogs}
          onConfirm={handleConfirmFinish}
          onDiscard={handleDiscard}
          onCancel={() => setShowSummary(false)}
          loading={finishing}
        />
      )}
    </div>
  )
}

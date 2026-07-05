import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Dumbbell, Activity, Flame, Zap, Clock } from 'lucide-react'
import { getSessions } from '../api/exercises'
import { startSession, saveActiveWorkout } from '../api/workoutSessions'
import { getHomeStats, type HomeStats } from '../api/stats'

const SESSION_META: Record<string, { focus: string }> = {
  'Push A': { focus: 'Chest · Shoulders · Triceps' },
  'Pull A': { focus: 'Back · Biceps · Rear Delts' },
  'Legs A': { focus: 'Quads · Glutes · Hamstrings' },
}

function fmtVol(v: number): string {
  return v >= 1000 ? `${(v / 1000).toFixed(1).replace(/\.0$/, '')}k` : `${v}`
}

function StatCard({
  icon: Icon, label, value, unit, delta, deltaUp,
}: {
  icon: React.ElementType
  label: string
  value: string | number
  unit: string
  delta?: string
  deltaUp?: boolean
}) {
  return (
    <div className="bg-[var(--color-surface)] rounded-[14px] p-[15px_16px] flex flex-col gap-[2px]"
      style={{ boxShadow: '0 1px 2px rgba(40,34,24,.04), 0 8px 24px rgba(40,34,24,.05)' }}>
      <div className="flex items-center gap-[7px] text-[var(--color-muted)] text-[12px] font-bold mb-[5px]">
        <Icon size={15} strokeWidth={2} />
        <span className="tracking-[0.05em] uppercase">{label}</span>
      </div>
      <div className="font-['DM_Mono',ui-monospace,monospace] text-[26px] font-medium leading-none tracking-[-0.01em]">
        {value}<span className="text-[13px] text-[var(--color-muted)] ml-[3px]">{unit}</span>
      </div>
      {delta && (
        <div className={`text-[11.5px] font-bold mt-[3px] ${deltaUp ? 'text-[var(--color-good)]' : 'text-[var(--color-accent)]'}`}>
          {delta}
        </div>
      )}
    </div>
  )
}

export default function HomePage() {
  const navigate = useNavigate()
  const [sessions, setSessions] = useState<string[]>([])
  const [starting, setStarting] = useState<string | null>(null)
  const [stats, setStats] = useState<HomeStats | null>(null)
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    Promise.all([getSessions(), getHomeStats()])
      .then(([s, h]) => { setSessions(s); setStats(h) })
      .catch(() => setLoadError(true))
  }, [])

  async function handleStart(session: string) {
    setStarting(session)
    try {
      const workout = await startSession(session)
      saveActiveWorkout(workout.id, session, workout.started_at)
      navigate(`/workout/${workout.id}`, { state: { session, sessionId: workout.id } })
    } finally {
      setStarting(null)
    }
  }

  const volumeDelta = stats
    ? stats.prev_week_volume === 0
      ? undefined
      : `${stats.week_volume >= stats.prev_week_volume ? '+' : ''}${Math.round((stats.week_volume - stats.prev_week_volume) / stats.prev_week_volume * 100)}% vs last`
    : undefined

  return (
    <div className="pb-6">
      <header className="px-4 pt-12 pb-4">
        <h1 className="text-[27px] font-extrabold tracking-tight">
          Fit<span className="text-[var(--color-accent)]">man</span>
        </h1>
      </header>

      <main className="px-4 space-y-4">

        {loadError && (
          <p className="text-sm text-red-500 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
            Could not load data — please check your connection and try again.
          </p>
        )}

        {/* Stats grid */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-[14px]">
            <StatCard
              icon={Flame}
              label="Streak"
              value={stats.streak}
              unit="days"
              delta={stats.streak > 0 ? 'Keep it up' : undefined}
              deltaUp
            />
            <StatCard
              icon={Dumbbell}
              label="This week"
              value={stats.week_workouts}
              unit="/ 5"
              delta={stats.week_workouts >= 3 ? 'On track' : undefined}
              deltaUp
            />
            <StatCard
              icon={Zap}
              label="Volume"
              value={fmtVol(stats.week_volume)}
              unit="kg"
              delta={volumeDelta}
              deltaUp={stats.week_volume >= stats.prev_week_volume}
            />
            <StatCard
              icon={Clock}
              label="Time"
              value={(stats.week_minutes / 60).toFixed(1).replace(/\.0$/, '')}
              unit="h"
              delta={stats.week_minutes > 0 ? `${stats.week_minutes} min` : undefined}
            />
          </div>
        )}

        {/* Session cards */}
        <div
          className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-2xl p-4 flex items-center justify-between"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[var(--color-accent)] bg-opacity-10 flex items-center justify-center">
              <Activity size={18} className="text-[var(--color-accent)]" />
            </div>
            <div>
              <p className="font-semibold text-[var(--color-text)]">Cardio</p>
              <p className="text-sm text-[var(--color-muted)]">Run · Bike · Swim · more</p>
            </div>
          </div>
          <button
            onClick={() => navigate('/cardio')}
            className="px-4 py-2 bg-[var(--color-accent)] text-white text-sm font-semibold rounded-xl"
          >
            Log
          </button>
        </div>

        {sessions.map(session => (
          <div
            key={session}
            className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-2xl p-4 flex items-center justify-between"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-[var(--color-accent)] bg-opacity-10 flex items-center justify-center">
                <Dumbbell size={18} className="text-[var(--color-accent)]" />
              </div>
              <div>
                <p className="font-semibold text-[var(--color-text)]">{session}</p>
                <p className="text-sm text-[var(--color-muted)]">
                  {SESSION_META[session]?.focus}
                </p>
              </div>
            </div>
            <button
              onClick={() => handleStart(session)}
              disabled={starting !== null}
              className="px-4 py-2 bg-[var(--color-accent)] text-white text-sm font-semibold rounded-xl disabled:opacity-50"
            >
              {starting === session ? '…' : 'Start'}
            </button>
          </div>
        ))}

      </main>
    </div>
  )
}

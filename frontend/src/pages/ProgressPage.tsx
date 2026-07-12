import { useEffect, useState } from 'react'
import { ResponsiveContainer, AreaChart, Area, BarChart, Bar, Cell, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'
import { Plus, Trash2, Award, ChevronRight } from 'lucide-react'
import bodyFrontUrl from '../assets/body_front.svg'
import {
  getStrengthProgression, getVolume, getPRs, getConsistency, getBalance,
  type StrengthData, type VolumePoint, type PersonalRecord,
  type ConsistencyWeek, type MuscleBalance,
} from '../api/progress'
import { getMeasurements, logMeasurement, deleteMeasurement, type Measurement } from '../api/measurements'

const DAY_LABELS = ['M', '', 'W', '', 'F', '', 'S']

const SESSION_RGB: Record<string, [number, number, number]> = {
  'Push A': [255, 90, 54],
  'Pull A': [59, 130, 246],
  'Legs A': [31, 157, 98],
}

function dayStyle(day: { trained: boolean; session: string | null; volume_kg: number | null }, maxVol: number): React.CSSProperties {
  if (!day.trained) return { background: 'var(--color-border)' }
  const rgb = SESSION_RGB[day.session ?? ''] ?? [255, 90, 54]
  const opacity = day.volume_kg && maxVol > 0 ? Math.max(0.25, Math.min(1, day.volume_kg / maxVol)) : 0.6
  return { background: `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${opacity})` }
}
const CARD_SHADOW = '0 1px 2px rgba(40,34,24,.04), 0 8px 24px rgba(40,34,24,.05)'

const MUSCLE_COLORS: Record<string, string> = {
  Quads: '#e8a020', Glutes: '#d49018', Hamstrings: '#c88020', Calves: '#b87018',
  Chest: '#e03030', 'Upper Chest': '#d02828',
  'Front Delt': '#e05828', 'Side Delt': '#d85028', 'Rear Delt': '#c84820',
  Triceps: '#c84828', Biceps: '#b84820', Brachialis: '#a84018',
  Lats: '#e06030', Traps: '#c05028',
  'Lower Back': '#905030',
}

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-[var(--color-surface)] rounded-[22px] p-[18px] ${className}`} style={{ boxShadow: CARD_SHADOW }}>
      {children}
    </div>
  )
}

function CardHead({ title, sub, right }: { title: string; sub?: string; right?: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-2 mb-[14px]">
      <div>
        <div className="text-[15.5px] font-bold tracking-[-0.01em] text-[var(--color-text)]">{title}</div>
        {sub && <div className="text-[12.5px] text-[var(--color-muted)] font-semibold mt-0.5">{sub}</div>}
      </div>
      {right && <div className="shrink-0">{right}</div>}
    </div>
  )
}

function Seg({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="inline-flex bg-[var(--color-border)] p-[3px] rounded-[11px] gap-0.5">
      {(['4W', '12W', '1Y'] as const).map(r => (
        <button
          key={r}
          onClick={() => onChange(r)}
          className={`px-[13px] py-[6px] rounded-[8px] text-[12.5px] font-bold transition-all ${
            value === r ? 'bg-[var(--color-surface)] text-[var(--color-text)]' : 'text-[var(--color-muted)]'
          }`}
          style={value === r ? { boxShadow: '0 1px 3px rgba(0,0,0,.08)' } : undefined}
        >
          {r}
        </button>
      ))}
    </div>
  )
}

type FigureItem = { label: string; left: boolean; topPct: number; value: number | null; tag: string; color: string }

const BODY_H = 280
const BODY_W = Math.round(BODY_H * 260 / 545)
const LABEL_W = 100

function BodyFigure({ title, items }: { title: string; items: FigureItem[] }) {
  const leftItems  = items.filter(i => i.left)
  const rightItems = items.filter(i => !i.left)
  return (
    <div className="flex-1 min-w-0 flex flex-col items-center">
      <div className="text-[13px] font-bold text-center mb-3 text-[var(--color-text)]">{title}</div>
      <div className="flex items-stretch gap-2">

        {/* Left labels */}
        <div className="relative shrink-0" style={{ width: LABEL_W, height: BODY_H }}>
          {leftItems.map(item => item.value != null && (
            <div key={item.label} className="absolute right-0 flex items-center gap-1.5"
              style={{ top: `${item.topPct}%`, transform: 'translateY(-50%)' }}>
              <div className="text-right">
                <div className="text-[13.5px] font-mono font-bold text-[var(--color-text)] leading-snug">
                  {item.value.toFixed(1)} kg
                </div>
                <div className="text-[11px] text-[var(--color-muted)] font-semibold leading-snug">{item.label}</div>
                <div className={`text-[11px] font-bold leading-snug ${item.color}`}>{item.tag}</div>
              </div>
              <div className="w-3 h-px shrink-0 bg-[var(--color-border)]" />
            </div>
          ))}
        </div>

        {/* Body image */}
        <div className="shrink-0" style={{ width: BODY_W, height: BODY_H }}>
          <img src={bodyFrontUrl} alt="" style={{ height: '100%', width: 'auto' }} />
        </div>

        {/* Right labels */}
        <div className="relative shrink-0" style={{ width: LABEL_W, height: BODY_H }}>
          {rightItems.map(item => item.value != null && (
            <div key={item.label} className="absolute left-0 flex items-center gap-1.5"
              style={{ top: `${item.topPct}%`, transform: 'translateY(-50%)' }}>
              <div className="w-3 h-px shrink-0 bg-[var(--color-border)]" />
              <div>
                <div className="text-[13.5px] font-mono font-bold text-[var(--color-text)] leading-snug">
                  {item.value.toFixed(1)} kg
                </div>
                <div className="text-[11px] text-[var(--color-muted)] font-semibold leading-snug">{item.label}</div>
                <div className={`text-[11px] font-bold leading-snug ${item.color}`}>{item.tag}</div>
              </div>
            </div>
          ))}
        </div>

      </div>
    </div>
  )
}

export default function ProgressPage() {
  const [selectedBodyMetric, setSelectedBodyMetric] = useState<string>('body_fat_pct')
  const [prs, setPRs] = useState<PersonalRecord[]>([])
  const [selectedExerciseId, setSelectedExerciseId] = useState<number | null>(null)
  const [strengthData, setStrengthData] = useState<StrengthData | null>(null)
  const [range, setRange] = useState<'4W' | '12W' | '1Y'>('12W')
  const [volume, setVolume] = useState<VolumePoint[]>([])
  const [consistency, setConsistency] = useState<ConsistencyWeek[]>([])
  const [balance, setBalance] = useState<MuscleBalance[]>([])
  const [measurements, setMeasurements] = useState<Measurement[]>([])
  const [loadError, setLoadError] = useState(false)
  const [showLogForm, setShowLogForm] = useState(false)
  const [weightInput, setWeightInput] = useState('')
  const [fatInput, setFatInput] = useState('')
  const [notesInput, setNotesInput] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    Promise.all([getPRs(), getVolume(), getConsistency(), getBalance(), getMeasurements()])
      .then(([prsData, vol, cons, bal, meas]) => {
        setPRs(prsData)
        if (prsData.length > 0) setSelectedExerciseId(prsData[0].exercise_id)
        setVolume(vol)
        setConsistency(cons)
        setBalance(bal)
        setMeasurements(meas)
      })
      .catch(() => setLoadError(true))
  }, [])

  useEffect(() => {
    if (selectedExerciseId !== null) {
      getStrengthProgression(selectedExerciseId)
        .then(setStrengthData)
        .catch(() => {})
    }
  }, [selectedExerciseId])

  // Range filter
  const rangeDays = { '4W': 28, '12W': 84, '1Y': 365 }
  const cutoff = new Date()
  cutoff.setDate(cutoff.getDate() - rangeDays[range])
  const cutoffStr = cutoff.toISOString().slice(0, 10)
  const filteredStrength = strengthData
    ? { ...strengthData, data: strengthData.data.filter(d => d.date >= cutoffStr) }
    : null

  const selectedPR = prs.find(p => p.exercise_id === selectedExerciseId) ?? null

  const volumeChartData = volume.map(v => ({
    ...v,
    week: v.week.split('-W')[1] ? `W${v.week.split('-W')[1]}` : v.week,
  }))

  const totalTrainedDays = consistency.reduce((sum, w) => sum + w.days.filter(d => d.trained).length, 0)
  const maxVolume = Math.max(...consistency.flatMap(w => w.days).map(d => d.volume_kg ?? 0), 1)

  const weightChartData = [...measurements]
    .reverse()
    .filter(m => m.weight_kg !== null)
    .map(m => ({ date: m.recorded_at.slice(0, 10), weight_kg: m.weight_kg }))

  const latestWeight = measurements.find(m => m.weight_kg != null)

  function toTrend(key: keyof typeof measurements[0]) {
    return [...measurements]
      .reverse()
      .filter(m => m[key] != null)
      .map(m => ({ date: m.recorded_at.slice(0, 10), value: m[key] as number }))
  }

  const allMetricData: Record<string, { date: string; value: number }[]> = {
    body_fat_pct:       toTrend('body_fat_pct'),
    fat_mass_kg:        toTrend('fat_mass_kg'),
    lean_mass_kg:       toTrend('lean_mass_kg'),
    skeletal_muscle_kg: toTrend('skeletal_muscle_kg'),
    bmi:                toTrend('bmi'),
    body_water_pct:     toTrend('body_water_pct'),
    bmr_kcal:           toTrend('bmr_kcal'),
    visceral_fat_grade: toTrend('visceral_fat_grade'),
    body_age:           toTrend('body_age'),
    whr_estimate:       toTrend('whr_estimate'),
  }

  async function handleLogMeasurement() {
    if (!weightInput && !fatInput) return
    setSaving(true)
    try {
      const created = await logMeasurement({
        weight_kg: weightInput ? parseFloat(weightInput) : null,
        body_fat_pct: fatInput ? parseFloat(fatInput) : null,
        notes: notesInput || null,
      })
      setMeasurements(prev => [created, ...prev])
      setWeightInput(''); setFatInput(''); setNotesInput('')
      setShowLogForm(false)
    } finally { setSaving(false) }
  }

  async function handleDelete(id: number) {
    await deleteMeasurement(id)
    setMeasurements(prev => prev.filter(m => m.id !== id))
  }

  const empty = <p className="text-[13.5px] text-[var(--color-faint)] text-center py-[30px] font-semibold">No data yet — log some workouts first.</p>

  return (
    <div className="pb-6">
      <header className="px-4 pt-12 pb-2">
        <h1 className="text-[27px] font-extrabold tracking-tight">Progress</h1>
        <p className="text-[13px] text-[var(--color-muted)] font-semibold mt-0.5">Your trends & records</p>
      </header>

      <main className="px-4 pt-4 space-y-4">

        {loadError && (
          <p className="text-sm text-red-500 bg-red-50 border border-red-200 rounded-xl px-4 py-3">
            Could not load data — please check your connection and try again.
          </p>
        )}

        {/* Strength */}
        <Card className="!p-[22px]">
          <CardHead
            title="Strength progression"
            sub={`Estimated 1-rep max · ${range}`}
            right={<Seg value={range} onChange={v => setRange(v as '4W' | '12W' | '1Y')} />}
          />
          {prs.length === 0 ? empty : (
            <>
              <div className="flex gap-2 overflow-x-auto pb-3 -mx-[22px] px-[22px]" style={{ scrollbarWidth: 'none' }}>
                {prs.map(pr => (
                  <button
                    key={pr.exercise_id}
                    onClick={() => setSelectedExerciseId(pr.exercise_id)}
                    className={`px-[13px] py-[7px] rounded-full text-[12.5px] font-semibold whitespace-nowrap border transition-colors ${
                      selectedExerciseId === pr.exercise_id
                        ? 'bg-[var(--color-text)] text-white border-[var(--color-text)]'
                        : 'bg-[var(--color-bg)] text-[var(--color-muted)] border-[var(--color-border)]'
                    }`}
                  >
                    {pr.exercise_name}
                  </button>
                ))}
              </div>

              {filteredStrength && filteredStrength.data.length > 1 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart data={filteredStrength.data}>
                    <defs>
                      <linearGradient id="strengthGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#ff5a36" stopOpacity={0.18} />
                        <stop offset="95%" stopColor="#ff5a36" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                    <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={d => d.slice(5)} />
                    <YAxis tick={{ fontSize: 11 }} unit=" kg" />
                    {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                    <Tooltip formatter={((v: number) => [`${v} kg`, 'Est. 1RM']) as any} />
                    <Area type="monotone" dataKey="estimated_1rm" stroke="#ff5a36" strokeWidth={2} fill="url(#strengthGrad)" dot={false} activeDot={{ r: 4, fill: '#ff5a36' }} />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-[13.5px] text-[var(--color-faint)] font-semibold py-6 text-center">
                  {strengthData && strengthData.data.length > 1 ? `No data in the last ${range}.` : 'Need at least 2 sessions to show a trend.'}
                </p>
              )}

              {selectedPR && (
                <div className="flex items-center justify-between mt-[14px] rounded-[14px] p-[13px_15px] bg-[var(--color-accent-soft)]">
                  <div className="flex items-center gap-[11px]">
                    <div className="w-[38px] h-[38px] rounded-[11px] bg-[var(--color-accent-soft)] text-[var(--color-accent)] flex items-center justify-center shrink-0">
                      <Award size={18} />
                    </div>
                    <div>
                      <div className="font-bold text-[14px] text-[var(--color-accent)]">Personal record</div>
                      <div className="text-[12.5px] text-[var(--color-muted)] font-semibold">{selectedPR.exercise_name} · {selectedPR.date}</div>
                    </div>
                  </div>
                  <div className="font-mono text-[24px] text-[var(--color-accent)]">
                    {selectedPR.estimated_1rm}<span className="text-[13px] text-[var(--color-muted)] ml-0.5">kg</span>
                  </div>
                </div>
              )}
            </>
          )}
        </Card>

        {/* Volume + Body weight — side by side on desktop */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

          <Card>
            <CardHead title="Training volume" sub="Total kg lifted per week" />
            {volumeChartData.length === 0 ? empty : (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={volumeChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} unit=" kg" />
                  {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                  <Tooltip formatter={((v: number) => [`${v.toLocaleString()} kg`, 'Volume']) as any} />
                  <Bar dataKey="volume_kg" radius={[4, 4, 0, 0]}>
                    {volumeChartData.map((_, i) => (
                      <Cell key={i} fill={i === volumeChartData.length - 1 ? '#ff5a36' : 'var(--color-border-strong)'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </Card>

          <Card>
            <CardHead
              title="Body weight"
              sub="kg over time"
              right={
                latestWeight?.weight_kg != null
                  ? <div className="font-mono text-[18px] text-[var(--color-text)]">{latestWeight.weight_kg}<span className="text-[12px] text-[var(--color-muted)] ml-0.5">kg</span></div>
                  : undefined
              }
            />

            <button
              onClick={() => setShowLogForm(v => !v)}
              className="flex items-center gap-1 text-[13px] font-semibold text-[var(--color-accent)] mb-3"
            >
              <Plus size={15} />Log measurement
            </button>

            {showLogForm && (
              <div className="bg-[var(--color-bg)] rounded-[14px] p-3 mb-3 space-y-2">
                <div className="flex gap-2">
                  <input type="number" step="0.1" min="0" placeholder="75.0 kg" value={weightInput}
                    onChange={e => setWeightInput(e.target.value)}
                    className="flex-1 px-3 py-2 rounded-[10px] border border-[var(--color-border)] bg-[var(--color-surface)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]" />
                  <input type="number" step="0.1" min="0" placeholder="18.0 %" value={fatInput}
                    onChange={e => setFatInput(e.target.value)}
                    className="flex-1 px-3 py-2 rounded-[10px] border border-[var(--color-border)] bg-[var(--color-surface)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]" />
                </div>
                <div className="flex gap-2">
                  <button onClick={handleLogMeasurement} disabled={saving || (!weightInput && !fatInput)}
                    className="flex-1 py-2 rounded-[10px] bg-[var(--color-accent)] text-white text-sm font-semibold disabled:opacity-40">
                    {saving ? 'Saving…' : 'Save'}
                  </button>
                  <button onClick={() => setShowLogForm(false)}
                    className="flex-1 py-2 rounded-[10px] border border-[var(--color-border)] text-sm text-[var(--color-muted)]">
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {weightChartData.length > 1 ? (
              <ResponsiveContainer width="100%" height={160}>
                <AreaChart data={weightChartData}>
                  <defs>
                    <linearGradient id="weightGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#1b1a17" stopOpacity={0.12} />
                      <stop offset="95%" stopColor="#1b1a17" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={d => d.slice(5)} />
                  <YAxis tick={{ fontSize: 11 }} unit=" kg" domain={['auto', 'auto']} />
                  {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                  <Tooltip formatter={((v: number) => [`${v} kg`, 'Weight']) as any} />
                  <Area type="monotone" dataKey="weight_kg" stroke="#1b1a17" strokeWidth={2} fill="url(#weightGrad)" dot={{ r: 3, fill: '#1b1a17' }} activeDot={{ r: 4, fill: '#1b1a17' }} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-[13.5px] text-[var(--color-faint)] font-semibold py-4 text-center">
                {weightChartData.length === 1 ? 'Need at least 2 entries to show a trend.' : 'Tap Log to add your first entry.'}
              </p>
            )}

            {measurements.length > 0 && (
              <div className="mt-3 space-y-1.5">
                {measurements.slice(0, 3).map(m => (
                  <div key={m.id} className="flex items-center justify-between text-[13px]">
                    <span className="font-semibold text-[var(--color-text)]">
                      {m.weight_kg != null ? `${m.weight_kg} kg` : '—'}
                      {m.body_fat_pct != null && <span className="text-[var(--color-muted)] font-normal ml-2">{m.body_fat_pct}% fat</span>}
                    </span>
                    <div className="flex items-center gap-3">
                      <span className="text-[var(--color-faint)] text-[12px]">{m.recorded_at.slice(0, 10)}</span>
                      <button onClick={() => handleDelete(m.id)} className="text-[var(--color-faint)] hover:text-red-500 transition-colors">
                        <Trash2 size={13} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Body composition — silhouette + key metrics */}
        {(() => {
          const latest = measurements[0]
          const prev = measurements[1]
          if (!latest?.bmi) return null

          const fatTotal = latest.fat_mass_kg ?? 1
          const muscleTotal = latest.skeletal_muscle_kg ?? 1
          const FAT_EXP  = { ra: 3.5, la: 3.5, rl: 18, ll: 18, trunk: 43 }
          const MUS_EXP  = { ra: 5,   la: 5,   rl: 22, ll: 22, trunk: 43 }

          function evalTag(val: number | null, total: number, exp: number): { tag: string; color: string } {
            if (!val || !total) return { tag: '—', color: 'text-[var(--color-muted)]' }
            const diff = (val / total) * 100 - exp
            if (diff > 4)  return { tag: 'High',     color: 'text-[#f97316]' }
            if (diff < -4) return { tag: 'Low',      color: 'text-[#60a5fa]' }
            return           { tag: 'Standard', color: 'text-[#22c55e]' }
          }

          const fatItems: FigureItem[] = [
            { label: 'L. Arm', left: true,  topPct: 32, value: latest.la_fat_kg,    ...evalTag(latest.la_fat_kg,    fatTotal, FAT_EXP.la) },
            { label: 'R. Arm', left: false, topPct: 32, value: latest.ra_fat_kg,    ...evalTag(latest.ra_fat_kg,    fatTotal, FAT_EXP.ra) },
            { label: 'Trunk',  left: true,  topPct: 51, value: latest.trunk_fat_kg, ...evalTag(latest.trunk_fat_kg, fatTotal, FAT_EXP.trunk) },
            { label: 'L. Leg', left: true,  topPct: 73, value: latest.ll_fat_kg,    ...evalTag(latest.ll_fat_kg,    fatTotal, FAT_EXP.ll) },
            { label: 'R. Leg', left: false, topPct: 73, value: latest.rl_fat_kg,    ...evalTag(latest.rl_fat_kg,    fatTotal, FAT_EXP.rl) },
          ]
          const muscleItems: FigureItem[] = [
            { label: 'L. Arm', left: true,  topPct: 32, value: latest.la_muscle_kg,    ...evalTag(latest.la_muscle_kg,    muscleTotal, MUS_EXP.la) },
            { label: 'R. Arm', left: false, topPct: 32, value: latest.ra_muscle_kg,    ...evalTag(latest.ra_muscle_kg,    muscleTotal, MUS_EXP.ra) },
            { label: 'Trunk',  left: true,  topPct: 51, value: latest.trunk_muscle_kg, ...evalTag(latest.trunk_muscle_kg, muscleTotal, MUS_EXP.trunk) },
            { label: 'L. Leg', left: true,  topPct: 73, value: latest.ll_muscle_kg,    ...evalTag(latest.ll_muscle_kg,    muscleTotal, MUS_EXP.ll) },
            { label: 'R. Leg', left: false, topPct: 73, value: latest.rl_muscle_kg,    ...evalTag(latest.rl_muscle_kg,    muscleTotal, MUS_EXP.rl) },
          ]

          function Trend({ curr, prev: p, lowerBetter = false }: { curr: number | null; prev: number | null; lowerBetter?: boolean }) {
            if (curr == null || p == null) return null
            const delta = curr - p
            if (Math.abs(delta) < 0.01) return null
            const up = delta > 0
            const good = lowerBetter ? !up : up
            return (
              <span className={`text-[11px] font-bold ml-1 ${good ? 'text-[#22c55e]' : 'text-[#f97316]'}`}>
                {up ? '↑' : '↓'} {Math.abs(delta).toFixed(1)}
              </span>
            )
          }

          return (
            <>
              <Card>
                <CardHead
                  title="Body composition"
                  sub={`Segmental analysis · ${latest.recorded_at.slice(0, 10)}`}
                />
                <div className="flex flex-col md:flex-row gap-6 md:gap-2">
                  <BodyFigure title="Segmental fat" items={fatItems} />
                  <div className="hidden md:block w-px bg-[var(--color-border)] shrink-0 self-stretch" />
                  <div className="block md:hidden h-px bg-[var(--color-border)]" />
                  <BodyFigure title="Muscle balance" items={muscleItems} />
                </div>
                <div className="flex gap-4 mt-3">
                  {[['#22c55e', 'Standard'], ['#f97316', 'High'], ['#60a5fa', 'Low']].map(([color, label]) => (
                    <div key={label} className="flex items-center gap-1.5">
                      <div className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
                      <span className="text-[10.5px] text-[var(--color-muted)] font-semibold">{label}</span>
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-[10.5px] text-[var(--color-faint)] leading-relaxed">
                  ⚠️ Segmental values are estimates from BIA research formulae. Not for medical use. Consult a healthcare professional.
                </p>
              </Card>

              <Card>
                {(() => {
                  const METRICS = [
                    { key: 'body_fat_pct',       label: 'Body fat',        unit: '%',     color: '#f97316', lowerBetter: true,  prev: prev?.body_fat_pct ?? null,       value: latest.body_fat_pct },
                    { key: 'fat_mass_kg',         label: 'Fat mass',        unit: ' kg',   color: '#f97316', lowerBetter: true,  prev: prev?.fat_mass_kg ?? null,         value: latest.fat_mass_kg },
                    { key: 'lean_mass_kg',        label: 'Lean mass',       unit: ' kg',   color: '#22c55e', lowerBetter: false, prev: prev?.lean_mass_kg ?? null,        value: latest.lean_mass_kg },
                    { key: 'skeletal_muscle_kg',  label: 'Skeletal muscle', unit: ' kg',   color: '#22c55e', lowerBetter: false, prev: prev?.skeletal_muscle_kg ?? null,  value: latest.skeletal_muscle_kg },
                    { key: 'bmi',                 label: 'BMI',             unit: '',      color: '#60a5fa', lowerBetter: true,  prev: prev?.bmi ?? null,                 value: latest.bmi },
                    { key: 'body_water_pct',      label: 'Body water',      unit: '%',     color: '#60a5fa', lowerBetter: false, prev: prev?.body_water_pct ?? null,      value: latest.body_water_pct },
                    { key: 'bmr_kcal',            label: 'BMR',             unit: ' kcal', color: '#22c55e', lowerBetter: false, prev: prev?.bmr_kcal ?? null,            value: latest.bmr_kcal },
                    { key: 'visceral_fat_grade',  label: 'Visceral fat',    unit: '',      color: '#f97316', lowerBetter: true,  prev: prev?.visceral_fat_grade ?? null,  value: latest.visceral_fat_grade },
                    { key: 'body_age',            label: 'Body age',        unit: ' yrs',  color: '#f97316', lowerBetter: true,  prev: prev?.body_age ?? null,            value: latest.body_age },
                    { key: 'whr_estimate',        label: 'WHR estimate',    unit: '',      color: '#f97316', lowerBetter: true,  prev: prev?.whr_estimate ?? null,        value: latest.whr_estimate },
                  ].filter(m => m.value != null)

                  const active = METRICS.find(m => m.key === selectedBodyMetric) ?? METRICS[0]
                  const activeData = allMetricData[active?.key ?? ''] ?? []

                  return (
                    <>
                      <CardHead title="Body metrics" sub={prev ? `vs ${prev.recorded_at.slice(0, 10)}` : 'Latest measurement'} />
                      <div className="flex flex-col md:flex-row gap-0 md:gap-6">

                        {/* Metric list */}
                        <div className="md:w-[42%] shrink-0">
                          {METRICS.map(m => {
                            const isSelected = m.key === (active?.key)
                            const hasChart = (allMetricData[m.key]?.length ?? 0) >= 2
                            const displayVal = typeof m.value === 'number'
                              ? m.unit === ' kcal' ? Math.round(m.value) : m.value.toFixed(m.unit === '' ? 1 : 1)
                              : m.value
                            return (
                              <div
                                key={m.key}
                                onClick={() => hasChart && setSelectedBodyMetric(m.key)}
                                className={`flex items-center justify-between py-[9px] border-b border-[var(--color-border)] last:border-0 rounded-lg px-2 -mx-2 transition-colors ${
                                  isSelected ? 'bg-[var(--color-accent-soft)]' : hasChart ? 'hover:bg-[var(--color-bg)] cursor-pointer' : ''
                                }`}
                              >
                                <span className={`text-[13px] font-semibold ${isSelected ? 'text-[var(--color-accent)]' : 'text-[var(--color-muted)]'}`}>
                                  {m.label}
                                </span>
                                <div className="flex items-center gap-1.5">
                                  <span className="text-[13.5px] font-bold text-[var(--color-text)]">
                                    {displayVal}{m.unit}
                                    <Trend curr={m.value as number} prev={m.prev} lowerBetter={m.lowerBetter} />
                                  </span>
                                  {hasChart && <ChevronRight size={13} className={isSelected ? 'text-[var(--color-accent)]' : 'text-[var(--color-faint)]'} />}
                                </div>
                              </div>
                            )
                          })}
                        </div>

                        {/* Chart */}
                        <div className="flex-1 mt-4 md:mt-0 flex flex-col justify-center">
                          {activeData.length >= 2 ? (
                            <>
                              <div className="text-[12px] text-[var(--color-muted)] font-semibold mb-2">
                                {active?.label} over time
                              </div>
                              <ResponsiveContainer width="100%" height={200}>
                                <AreaChart data={activeData}>
                                  <defs>
                                    <linearGradient id="metricGrad" x1="0" y1="0" x2="0" y2="1">
                                      <stop offset="5%" stopColor={active?.color} stopOpacity={0.18} />
                                      <stop offset="95%" stopColor={active?.color} stopOpacity={0} />
                                    </linearGradient>
                                  </defs>
                                  <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
                                  <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={d => d.slice(5)} />
                                  <YAxis tick={{ fontSize: 10 }} unit={active?.unit} domain={['auto', 'auto']} />
                                  {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                                  <Tooltip formatter={((v: number) => [`${active?.unit === ' kcal' ? Math.round(v) : v}${active?.unit}`, active?.label]) as any} />
                                  <Area type="monotone" dataKey="value" stroke={active?.color} strokeWidth={2} fill="url(#metricGrad)" dot={{ r: 3, fill: active?.color }} activeDot={{ r: 4 }} />
                                </AreaChart>
                              </ResponsiveContainer>
                            </>
                          ) : (
                            <div className="flex items-center justify-center h-full min-h-[140px] text-[13px] text-[var(--color-faint)] font-semibold text-center px-4">
                              Select a metric with 2+ measurements to see its trend.
                            </div>
                          )}
                        </div>

                      </div>
                    </>
                  )
                })()}
              </Card>
            </>
          )
        })()}

        {/* Consistency + Balance — side by side on desktop */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

          <Card>
            <CardHead
              title="Consistency"
              sub="Last 17 weeks"
              right={consistency.length > 0
                ? <span className="text-[12px] text-[var(--color-muted)] font-semibold">{totalTrainedDays} days</span>
                : undefined}
            />
            {consistency.length === 0 ? empty : (
              <>
                <div className="flex gap-2 items-start">
                  {/* Day labels */}
                  <div className="shrink-0" style={{ display: 'grid', gridTemplateRows: 'repeat(7, 14px)', gap: 3 }}>
                    {DAY_LABELS.map((label, i) => (
                      <div key={i} className="text-[9px] text-[var(--color-muted)] flex items-center justify-end pr-1 w-4" style={{ height: 14 }}>
                        {label}
                      </div>
                    ))}
                  </div>
                  {/* Column-flow grid — weeks as columns, days as rows */}
                  <div
                    className="flex-1 overflow-x-auto"
                    style={{ display: 'grid', gridAutoFlow: 'column', gridTemplateRows: 'repeat(7, 14px)', gap: 3 }}
                  >
                    {consistency.flatMap(week => week.days).map(day => (
                      <div
                        key={day.date}
                        title={`${day.date}${day.session ? ` · ${day.session}` : ''}${day.volume_kg ? ` · ${day.volume_kg} kg` : ''}`}
                        style={{ width: 14, height: 14, borderRadius: 3, ...dayStyle(day, maxVolume) }}
                      />
                    ))}
                  </div>
                </div>
                {/* Legend */}
                <div className="flex items-center gap-4 mt-3 flex-wrap">
                  {Object.entries(SESSION_RGB).map(([label, rgb]) => (
                    <div key={label} className="flex items-center gap-1.5">
                      <div className="w-3 h-3 rounded-[3px]" style={{ background: `rgb(${rgb[0]},${rgb[1]},${rgb[2]})` }} />
                      <span className="text-[11px] font-semibold text-[var(--color-muted)]">{label}</span>
                    </div>
                  ))}
                  <div className="flex items-center gap-1 ml-auto">
                    <span className="text-[10px] text-[var(--color-faint)]">Less</span>
                    {[0.25, 0.5, 0.75, 1].map(o => (
                      <div key={o} className="w-3 h-3 rounded-[3px]" style={{ background: `rgba(255,90,54,${o})` }} />
                    ))}
                    <span className="text-[10px] text-[var(--color-faint)]">More</span>
                  </div>
                </div>
              </>
            )}
          </Card>

          <Card>
            <CardHead title="Muscle balance" sub="Share of weekly volume" />
            {balance.length === 0 ? empty : (
              <div>
                {balance.map(b => (
                  <div key={b.muscle} className="grid items-center gap-3 py-[7px]" style={{ gridTemplateColumns: '78px 1fr 42px' }}>
                    <div className="text-[13px] font-bold text-[var(--color-text)] truncate">{b.muscle}</div>
                    <div className="h-[10px] rounded-full bg-[var(--color-bg)] overflow-hidden">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${(b.percentage / balance[0].percentage) * 100}%`,
                          background: MUSCLE_COLORS[b.muscle] ?? '#ff5a36',
                        }}
                      />
                    </div>
                    <div className="font-mono text-[12.5px] text-[var(--color-muted)] text-right">{b.percentage}%</div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>

        {/* Personal Records */}
        <Card>
          <CardHead
            title="Personal records"
            sub="All-time bests"
            right={<Award size={18} className="text-[var(--color-accent)]" />}
          />
          {prs.length === 0 ? empty : (
            <div>
              {prs.map((pr, i) => (
                <div key={pr.exercise_id} className={`flex items-center gap-3 py-[11px] ${i > 0 ? 'border-t border-[var(--color-border)]' : ''}`}>
                  <div className="w-[38px] h-[38px] rounded-[11px] bg-[var(--color-accent-soft)] text-[var(--color-accent)] flex items-center justify-center shrink-0">
                    <Award size={18} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-bold text-[14px] text-[var(--color-text)] truncate">{pr.exercise_name}</div>
                    <div className="text-[12px] text-[var(--color-muted)] font-semibold mt-0.5">{pr.date}</div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono text-[17px] text-[var(--color-text)]">
                      {pr.weight} <span className="text-[11px] text-[var(--color-muted)]">kg × {pr.reps}</span>
                    </div>
                    <div className="text-[11.5px] font-bold text-[var(--color-good)]">~{pr.estimated_1rm} kg 1RM</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

      </main>
    </div>
  )
}

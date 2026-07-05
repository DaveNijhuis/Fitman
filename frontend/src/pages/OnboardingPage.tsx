import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { updateProfile } from '../api/profile'

const inputCls = 'w-full px-3 py-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]'
const labelCls = 'text-xs text-[var(--color-muted)] mb-1.5 block'

export const ONBOARDING_FLAG = 'fitman_onboarding_pending'

export default function OnboardingPage() {
  const navigate = useNavigate()

  const [displayName, setDisplayName] = useState('')
  const [birthYear, setBirthYear]     = useState('')
  const [sex, setSex]                 = useState('')
  const [heightCm, setHeightCm]       = useState('')
  const [saving, setSaving]           = useState(false)
  const [error, setError]             = useState<string | null>(null)

  function finish() {
    localStorage.removeItem(ONBOARDING_FLAG)
    navigate('/', { replace: true })
  }

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      await updateProfile({
        display_name: displayName || null,
        birth_year:   birthYear ? parseInt(birthYear, 10) : null,
        sex:          (sex as 'male' | 'female' | 'other') || null,
        height_cm:    heightCm ? parseFloat(heightCm) : null,
      })
      finish()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed.')
      setSaving(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-6">

        <div className="text-center space-y-1">
          <h1 className="text-3xl font-bold tracking-tight">
            Welcome to Fit<span className="text-[var(--color-accent)]">man</span>
          </h1>
          <p className="text-sm text-[var(--color-muted)]">
            A few optional details personalise your progress insights and body composition calculations.
          </p>
        </div>

        <div className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-4 space-y-4">
          <div>
            <label className={labelCls}>Display name</label>
            <input
              type="text"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              placeholder="e.g. Dave"
              className={inputCls}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Birth year</label>
              <input
                type="text"
                inputMode="numeric"
                value={birthYear}
                onChange={e => setBirthYear(e.target.value)}
                placeholder="1990"
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>Height (cm)</label>
              <input
                type="text"
                inputMode="decimal"
                value={heightCm}
                onChange={e => setHeightCm(e.target.value)}
                placeholder="180"
                className={inputCls}
              />
            </div>
          </div>
          <div>
            <label className={labelCls}>Sex</label>
            <select value={sex} onChange={e => setSex(e.target.value)} className={inputCls}>
              <option value="">Prefer not to say</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other</option>
            </select>
          </div>

          {error && <p className="text-sm text-red-500">{error}</p>}

          <button
            onClick={handleSave}
            disabled={saving}
            className="w-full py-3 bg-[var(--color-accent)] text-white font-semibold rounded-xl disabled:opacity-40"
          >
            {saving ? 'Saving…' : 'Save & continue'}
          </button>
          <button
            onClick={finish}
            className="w-full py-2 text-sm text-[var(--color-muted)] hover:text-[var(--color-text)] transition-colors"
          >
            Skip for now
          </button>
        </div>

        <p className="text-center text-[11px] text-[var(--color-faint)]">
          You can update these at any time in Settings.
        </p>
      </div>
    </div>
  )
}

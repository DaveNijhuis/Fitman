import { useEffect, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, Download, Trash2, AlertTriangle, ShieldCheck } from 'lucide-react'
import { getProfile, updateProfile, changePassword, type Profile } from '../api/profile'
import { exportData, eraseAccount } from '../api/gdpr'
import { logout } from '../api/auth'

const inputCls = 'w-full px-3 py-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]'
const labelCls = 'text-xs text-[var(--color-muted)] mb-1.5 block'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-4 space-y-4">
      <h2 className="text-base font-semibold text-[var(--color-text)]">{title}</h2>
      {children}
    </section>
  )
}

function Feedback({ msg }: { msg: { type: 'ok' | 'err'; text: string } | null }) {
  if (!msg) return null
  return (
    <p className={`text-sm ${msg.type === 'ok' ? 'text-green-600' : 'text-red-500'}`}>
      {msg.text}
    </p>
  )
}

export default function SettingsPage() {
  const navigate = useNavigate()

  // Profile
  const [profile, setProfile] = useState<Profile | null>(null)
  const [displayName, setDisplayName] = useState('')
  const [birthYear, setBirthYear] = useState('')
  const [sex, setSex] = useState('')
  const [heightCm, setHeightCm] = useState('')
  const [profileSaving, setProfileSaving] = useState(false)
  const [profileMsg, setProfileMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)

  // Password
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [pwSaving, setPwSaving] = useState(false)
  const [pwMsg, setPwMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)

  // GDPR
  const [exporting, setExporting] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleteConfirmText, setDeleteConfirmText] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [gdprErr, setGdprErr] = useState<string | null>(null)

  useEffect(() => {
    getProfile()
      .then(p => {
        setProfile(p)
        setDisplayName(p.display_name ?? '')
        setBirthYear(p.birth_year?.toString() ?? '')
        setSex(p.sex ?? '')
        setHeightCm(p.height_cm?.toString() ?? '')
      })
      .catch(() => {})
  }, [])

  async function handleProfileSave() {
    setProfileSaving(true)
    setProfileMsg(null)
    try {
      const updated = await updateProfile({
        display_name: displayName || null,
        birth_year: birthYear ? parseInt(birthYear, 10) : null,
        sex: (sex as 'male' | 'female' | 'other') || null,
        height_cm: heightCm ? parseFloat(heightCm) : null,
      })
      setProfile(updated)
      setProfileMsg({ type: 'ok', text: 'Profile saved.' })
    } catch (err) {
      setProfileMsg({ type: 'err', text: err instanceof Error ? err.message : 'Save failed.' })
    } finally {
      setProfileSaving(false)
    }
  }

  async function handlePasswordChange() {
    setPwMsg(null)
    if (newPw.length < 8) {
      setPwMsg({ type: 'err', text: 'New password must be at least 8 characters.' })
      return
    }
    if (newPw !== confirmPw) {
      setPwMsg({ type: 'err', text: 'Passwords do not match.' })
      return
    }
    setPwSaving(true)
    try {
      await changePassword(currentPw, newPw)
      setCurrentPw('')
      setNewPw('')
      setConfirmPw('')
      setPwMsg({ type: 'ok', text: 'Password changed.' })
    } catch (err) {
      setPwMsg({ type: 'err', text: err instanceof Error ? err.message : 'Change failed.' })
    } finally {
      setPwSaving(false)
    }
  }

  async function handleExport() {
    setExporting(true)
    setGdprErr(null)
    try {
      await exportData()
    } catch {
      setGdprErr('Export failed. Please try again.')
    } finally {
      setExporting(false)
    }
  }

  async function handleErase() {
    setDeleting(true)
    try {
      await eraseAccount()
      logout()
      window.location.href = '/'
    } catch {
      setGdprErr('Deletion failed. Please try again.')
      setDeleting(false)
      setConfirmDelete(false)
    }
  }

  return (
    <div className="min-h-screen pb-8">
      <header className="px-4 pt-12 pb-6 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-[var(--color-muted)] md:hidden">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        {profile?.is_admin && (
          <span className="ml-1 px-2 py-0.5 rounded-full bg-[var(--color-accent-soft)] text-[var(--color-accent)] text-xs font-semibold">
            Admin
          </span>
        )}
      </header>

      <main className="px-4 space-y-6">

        {/* Admin panel link — only for admins */}
        {profile?.is_admin && (
          <Link
            to="/admin"
            className="flex items-center justify-between px-4 py-3 bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] hover:bg-[var(--color-bg)] transition-colors"
          >
            <div className="flex items-center gap-3">
              <ShieldCheck size={18} className="text-[var(--color-accent)]" />
              <span className="text-sm font-semibold text-[var(--color-text)]">Admin panel</span>
            </div>
            <span className="text-xs text-[var(--color-muted)]">Manage users →</span>
          </Link>
        )}

        {/* Profile */}
        <Section title="Profile">
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
              <option value="">Not set</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other</option>
            </select>
          </div>
          <Feedback msg={profileMsg} />
          <button
            onClick={handleProfileSave}
            disabled={profileSaving}
            className="w-full py-3 bg-[var(--color-accent)] text-white font-semibold rounded-xl disabled:opacity-40"
          >
            {profileSaving ? 'Saving…' : 'Save profile'}
          </button>
        </Section>

        {/* Password */}
        <Section title="Change password">
          <div>
            <label className={labelCls}>Current password</label>
            <input
              type="password"
              value={currentPw}
              onChange={e => setCurrentPw(e.target.value)}
              autoComplete="current-password"
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>New password</label>
            <input
              type="password"
              value={newPw}
              onChange={e => setNewPw(e.target.value)}
              autoComplete="new-password"
              className={inputCls}
            />
          </div>
          <div>
            <label className={labelCls}>Confirm new password</label>
            <input
              type="password"
              value={confirmPw}
              onChange={e => setConfirmPw(e.target.value)}
              autoComplete="new-password"
              className={inputCls}
            />
          </div>
          <Feedback msg={pwMsg} />
          <button
            onClick={handlePasswordChange}
            disabled={pwSaving || !currentPw || !newPw || !confirmPw}
            className="w-full py-3 bg-[var(--color-accent)] text-white font-semibold rounded-xl disabled:opacity-40"
          >
            {pwSaving ? 'Changing…' : 'Change password'}
          </button>
        </Section>

        {/* Data & Privacy */}
        <Section title="Data & privacy">
          <p className="text-sm text-[var(--color-muted)]">
            Your data is stored exclusively on this server. You can export a full copy or permanently delete your account at any time.
          </p>
          <button
            onClick={handleExport}
            disabled={exporting}
            className="w-full flex items-center justify-center gap-2 py-3 border border-[var(--color-border)] rounded-xl text-sm font-semibold text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-colors disabled:opacity-40"
          >
            <Download size={16} />
            {exporting ? 'Preparing export…' : 'Download my data'}
          </button>

          {!confirmDelete ? (
            <button
              onClick={() => setConfirmDelete(true)}
              className="w-full flex items-center justify-center gap-2 py-3 border border-red-200 rounded-xl text-sm font-semibold text-red-500 hover:bg-red-50 transition-colors"
            >
              <Trash2 size={16} />
              Delete my account
            </button>
          ) : (
            <div className="space-y-3 border border-red-200 rounded-xl p-4 bg-red-50">
              <div className="flex items-start gap-2 text-red-700">
                <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                <p className="text-sm font-medium">
                  This will permanently delete your account, all workout sessions, measurements, and logs. This cannot be undone.
                </p>
              </div>
              <div>
                <label className="text-xs font-semibold text-red-700 block mb-1.5">
                  Type <span className="font-mono">DELETE</span> to confirm
                </label>
                <input
                  type="text"
                  value={deleteConfirmText}
                  onChange={e => setDeleteConfirmText(e.target.value)}
                  placeholder="DELETE"
                  className="w-full px-3 py-2 rounded-xl border border-red-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-red-400 font-mono"
                  autoComplete="off"
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => { setConfirmDelete(false); setDeleteConfirmText('') }}
                  className="flex-1 py-2 rounded-xl border border-[var(--color-border)] text-sm font-semibold text-[var(--color-muted)] hover:bg-[var(--color-bg)] transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleErase}
                  disabled={deleting || deleteConfirmText !== 'DELETE'}
                  className="flex-1 py-2 rounded-xl bg-red-500 text-white text-sm font-semibold disabled:opacity-40 transition-opacity"
                >
                  {deleting ? 'Deleting…' : 'Yes, delete everything'}
                </button>
              </div>
            </div>
          )}

          {gdprErr && <p className="text-sm text-red-500">{gdprErr}</p>}
        </Section>

      </main>
    </div>
  )
}

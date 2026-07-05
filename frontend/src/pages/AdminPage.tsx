import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Trash2, UserPlus, ShieldCheck, ShieldOff, ToggleLeft, ToggleRight } from 'lucide-react'
import { listUsers, createUser, patchUser, deleteUser, type AdminUser } from '../api/admin'
import { getProfile } from '../api/profile'

const inputCls = 'w-full px-3 py-2 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg)] text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]'
const labelCls = 'text-xs text-[var(--color-muted)] mb-1.5 block'

export default function AdminPage() {
  const navigate = useNavigate()
  const [currentUserId, setCurrentUserId] = useState<number | null>(null)
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Invite form
  const [showInvite, setShowInvite] = useState(false)
  const [inviteUsername, setInviteUsername] = useState('')
  const [invitePassword, setInvitePassword] = useState('')
  const [inviteDisplayName, setInviteDisplayName] = useState('')
  const [inviteIsAdmin, setInviteIsAdmin] = useState(false)
  const [inviteSaving, setInviteSaving] = useState(false)
  const [inviteMsg, setInviteMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)

  // Delete confirmation
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    Promise.all([getProfile(), listUsers()])
      .then(([profile, userList]) => {
        // We need the current user's id — fetch it from the user list by username
        const me = userList.find(u => u.username === profile.username)
        setCurrentUserId(me?.id ?? null)
        setUsers(userList)
      })
      .catch(() => setError('Failed to load users.'))
      .finally(() => setLoading(false))
  }, [])

  async function handleInvite() {
    setInviteMsg(null)
    setInviteSaving(true)
    try {
      const newUser = await createUser({
        username: inviteUsername,
        password: invitePassword,
        display_name: inviteDisplayName || null,
        is_admin: inviteIsAdmin,
      })
      setUsers(prev => [...prev, newUser])
      setInviteUsername('')
      setInvitePassword('')
      setInviteDisplayName('')
      setInviteIsAdmin(false)
      setShowInvite(false)
      setInviteMsg({ type: 'ok', text: `User "${newUser.username}" created.` })
    } catch (err) {
      setInviteMsg({ type: 'err', text: err instanceof Error ? err.message : 'Failed to create user.' })
    } finally {
      setInviteSaving(false)
    }
  }

  async function handleToggleActive(user: AdminUser) {
    try {
      const updated = await patchUser(user.id, { is_active: !user.is_active })
      setUsers(prev => prev.map(u => u.id === updated.id ? updated : u))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed.')
    }
  }

  async function handleToggleAdmin(user: AdminUser) {
    try {
      const updated = await patchUser(user.id, { is_admin: !user.is_admin })
      setUsers(prev => prev.map(u => u.id === updated.id ? updated : u))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Update failed.')
    }
  }

  async function handleDelete(id: number) {
    setDeleting(true)
    try {
      await deleteUser(id)
      setUsers(prev => prev.filter(u => u.id !== id))
      setConfirmDeleteId(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed.')
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="min-h-screen pb-8">
      <header className="px-4 pt-12 pb-6 flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-[var(--color-muted)] md:hidden">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-2xl font-bold tracking-tight">Admin</h1>
        <span className="ml-1 px-2 py-0.5 rounded-full bg-[var(--color-accent-soft)] text-[var(--color-accent)] text-xs font-semibold">
          Admin
        </span>
      </header>

      <main className="px-4 space-y-6">

        {error && (
          <p className="text-sm text-red-500">{error}</p>
        )}

        {/* User list */}
        <section className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
            <h2 className="text-base font-semibold">Users</h2>
            <button
              onClick={() => { setShowInvite(v => !v); setInviteMsg(null) }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-[var(--color-accent)] text-white text-sm font-semibold"
            >
              <UserPlus size={14} />
              Invite
            </button>
          </div>

          {/* Invite form */}
          {showInvite && (
            <div className="px-4 py-4 border-b border-[var(--color-border)] space-y-3 bg-[var(--color-bg)]">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={labelCls}>Username</label>
                  <input
                    type="text"
                    value={inviteUsername}
                    onChange={e => setInviteUsername(e.target.value)}
                    className={inputCls}
                    autoComplete="off"
                  />
                </div>
                <div>
                  <label className={labelCls}>Temporary password</label>
                  <input
                    type="text"
                    value={invitePassword}
                    onChange={e => setInvitePassword(e.target.value)}
                    className={inputCls}
                    autoComplete="off"
                  />
                </div>
              </div>
              <div>
                <label className={labelCls}>Display name (optional)</label>
                <input
                  type="text"
                  value={inviteDisplayName}
                  onChange={e => setInviteDisplayName(e.target.value)}
                  className={inputCls}
                />
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={inviteIsAdmin}
                  onChange={e => setInviteIsAdmin(e.target.checked)}
                  className="accent-[var(--color-accent)]"
                />
                <span className="text-sm text-[var(--color-muted)]">Grant admin access</span>
              </label>
              {inviteMsg && (
                <p className={`text-sm ${inviteMsg.type === 'ok' ? 'text-green-600' : 'text-red-500'}`}>
                  {inviteMsg.text}
                </p>
              )}
              <div className="flex gap-2">
                <button
                  onClick={() => setShowInvite(false)}
                  className="flex-1 py-2 rounded-xl border border-[var(--color-border)] text-sm font-semibold text-[var(--color-muted)]"
                >
                  Cancel
                </button>
                <button
                  onClick={handleInvite}
                  disabled={inviteSaving || !inviteUsername || invitePassword.length < 8}
                  className="flex-1 py-2 rounded-xl bg-[var(--color-accent)] text-white text-sm font-semibold disabled:opacity-40"
                >
                  {inviteSaving ? 'Creating…' : 'Create user'}
                </button>
              </div>
            </div>
          )}

          {inviteMsg?.type === 'ok' && !showInvite && (
            <p className="px-4 py-2 text-sm text-green-600 border-b border-[var(--color-border)]">{inviteMsg.text}</p>
          )}

          {/* User rows */}
          {loading ? (
            <p className="px-4 py-6 text-sm text-[var(--color-muted)]">Loading…</p>
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {users.map(user => (
                <li key={user.id} className="px-4 py-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-semibold text-[var(--color-text)] truncate">
                          {user.username}
                        </span>
                        {user.display_name && (
                          <span className="text-xs text-[var(--color-muted)]">{user.display_name}</span>
                        )}
                        {user.is_admin && (
                          <span className="px-1.5 py-0.5 rounded-full bg-[var(--color-accent-soft)] text-[var(--color-accent)] text-[10px] font-semibold">
                            Admin
                          </span>
                        )}
                        {!user.is_active && (
                          <span className="px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-400 text-[10px] font-semibold">
                            Disabled
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-[var(--color-muted)] mt-0.5">
                        Joined {user.created_at.slice(0, 10)}
                        {user.email && ` · ${user.email}`}
                      </p>
                    </div>

                    {/* Actions — hidden for self */}
                    {user.id !== currentUserId && (
                      <div className="flex items-center gap-1 shrink-0">
                        <button
                          onClick={() => handleToggleActive(user)}
                          title={user.is_active ? 'Disable account' : 'Enable account'}
                          className="p-1.5 rounded-lg text-[var(--color-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-colors"
                        >
                          {user.is_active
                            ? <ToggleRight size={18} className="text-green-500" />
                            : <ToggleLeft size={18} />
                          }
                        </button>
                        <button
                          onClick={() => handleToggleAdmin(user)}
                          title={user.is_admin ? 'Remove admin' : 'Make admin'}
                          className="p-1.5 rounded-lg text-[var(--color-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-colors"
                        >
                          {user.is_admin
                            ? <ShieldCheck size={18} className="text-[var(--color-accent)]" />
                            : <ShieldOff size={18} />
                          }
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(user.id)}
                          title="Delete user"
                          className="p-1.5 rounded-lg text-[var(--color-muted)] hover:text-red-500 hover:bg-red-50 transition-colors"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Delete confirmation inline */}
                  {confirmDeleteId === user.id && (
                    <div className="mt-3 flex items-center gap-2 p-3 rounded-xl border border-red-200 bg-red-50">
                      <p className="text-xs text-red-700 flex-1">
                        Delete <strong>{user.username}</strong> and all their data?
                      </p>
                      <button
                        onClick={() => setConfirmDeleteId(null)}
                        className="px-3 py-1.5 rounded-lg border border-[var(--color-border)] text-xs font-semibold text-[var(--color-muted)]"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleDelete(user.id)}
                        disabled={deleting}
                        className="px-3 py-1.5 rounded-lg bg-red-500 text-white text-xs font-semibold disabled:opacity-40"
                      >
                        {deleting ? '…' : 'Delete'}
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

      </main>
    </div>
  )
}

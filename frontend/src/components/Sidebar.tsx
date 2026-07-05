import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { House, TrendingUp, Clock, BookOpen, Zap, Plus, Play, Settings } from 'lucide-react'
import { getActiveWorkout } from '../api/workoutSessions'

const NAV = [
  { label: 'Home',      icon: House,       path: '/' },
  { label: 'Progress',  icon: TrendingUp,  path: '/progress' },
  { label: 'History',   icon: Clock,       path: '/history' },
  { label: 'Library',   icon: BookOpen,    path: '/library' },
]

export default function Sidebar() {
  const navigate = useNavigate()
  useLocation() // re-render on navigation to pick up localStorage changes

  const active = getActiveWorkout()

  return (
    <aside className="hidden md:flex flex-col w-[236px] shrink-0 bg-[var(--color-surface)] border-r border-[var(--color-border)] h-full px-4 py-[26px]">

      {/* Brand */}
      <div className="flex items-center gap-[10px] px-[10px] pb-[26px]">
        <div className="w-[30px] h-[30px] rounded-[9px] bg-[var(--color-accent)] flex items-center justify-center">
          <Zap size={16} color="#fff" strokeWidth={2.2} />
        </div>
        <span className="font-extrabold text-[19px] tracking-tight text-[var(--color-text)]">Fitman</span>
      </div>

      {/* Nav list */}
      <nav className="flex flex-col gap-[3px]">
        {NAV.map(({ label, icon: Icon, path }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-[10px] rounded-xl font-semibold text-[14.5px] transition-colors ${
                isActive
                  ? 'bg-[var(--color-accent-soft)] text-[var(--color-accent)]'
                  : 'text-[var(--color-muted)] hover:bg-[var(--color-bg)] hover:text-[var(--color-text)]'
              }`
            }
          >
            <Icon size={20} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* CTA pinned to bottom */}
      <div className="mt-auto flex flex-col gap-2">
        <button
          onClick={() => active
            ? navigate(`/workout/${active.id}`, { state: { session: active.session, sessionId: active.id } })
            : navigate('/')
          }
          className="flex items-center justify-center gap-2 w-full py-[13px] px-[18px] rounded-[14px] bg-[var(--color-accent)] text-white font-bold text-[15px]"
        >
          {active ? <Play size={18} strokeWidth={2.2} fill="#fff" /> : <Plus size={18} strokeWidth={2.2} />}
          {active ? `Resume ${active.session}` : 'Start workout'}
        </button>
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `flex items-center gap-3 px-3 py-[10px] rounded-xl font-semibold text-[14.5px] transition-colors ${
              isActive
                ? 'bg-[var(--color-accent-soft)] text-[var(--color-accent)]'
                : 'text-[var(--color-muted)] hover:bg-[var(--color-bg)] hover:text-[var(--color-text)]'
            }`
          }
        >
          <Settings size={20} />
          Settings
        </NavLink>
      </div>
    </aside>
  )
}

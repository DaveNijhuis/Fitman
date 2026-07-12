import { useEffect, useState } from 'react'
import { NavLink, useNavigate, useLocation } from 'react-router-dom'
import { House, TrendingUp, Clock, BookOpen, Plus, Play, Settings, Dumbbell } from 'lucide-react'
import { getActiveWorkout } from '../api/workoutSessions'
import SessionPickerSheet from './SessionPickerSheet'

const LEFT  = [
  { label: 'Home',     icon: House,      path: '/' },
  { label: 'Progress', icon: TrendingUp, path: '/progress' },
]
const RIGHT = [
  { label: 'History',  icon: Clock,      path: '/history' },
  { label: 'Library',  icon: BookOpen,   path: '/library' },
]

export default function BottomNav() {
  const navigate  = useNavigate()
  const location  = useLocation()

  const active = getActiveWorkout()
  const [fabOpen, setFabOpen]     = useState(false)
  const [showPicker, setShowPicker] = useState(false)

  // Close speed-dial whenever the route changes (nav tab tap, etc.)
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { setFabOpen(false) }, [location.pathname])

  const menuItems = active
    ? [
        {
          label: 'Continue workout',
          Icon: Play,
          accent: true,
          action: () => {
            setFabOpen(false)
            navigate(`/workout/${active.id}`, { state: { session: active.session, sessionId: active.id } })
          },
        },
        {
          label: 'Settings',
          Icon: Settings,
          accent: false,
          action: () => { setFabOpen(false); navigate('/settings') },
        },
      ]
    : [
        {
          label: 'Start workout',
          Icon: Dumbbell,
          accent: true,
          action: () => { setFabOpen(false); setShowPicker(true) },
        },
        {
          label: 'Settings',
          Icon: Settings,
          accent: false,
          action: () => { setFabOpen(false); navigate('/settings') },
        },
      ]

  const tab = (label: string, Icon: React.ElementType, path: string) => (
    <NavLink
      key={path}
      to={path}
      end={path === '/'}
      className={({ isActive }) =>
        `flex flex-col items-center gap-1 flex-1 text-[10.5px] font-semibold py-[2px] transition-colors ${
          isActive ? 'text-[var(--color-accent)]' : 'text-[var(--color-faint)]'
        }`
      }
    >
      {({ isActive }) => (
        <>
          <Icon size={23} strokeWidth={isActive ? 2.2 : 1.9} />
          {label}
        </>
      )}
    </NavLink>
  )

  return (
    <>
      {showPicker && <SessionPickerSheet onClose={() => setShowPicker(false)} />}

      {/* Backdrop — below nav (z-[25]) so the nav stays visible above it */}
      {fabOpen && (
        <div
          className="fixed inset-0 z-[25] bg-black/20"
          onClick={() => setFabOpen(false)}
        />
      )}

      <nav
        className="md:hidden relative z-30 shrink-0 flex justify-around items-stretch px-[10px] pt-[9px] pb-[26px] border-t border-[var(--color-border)]"
        style={{ background: 'rgba(255,255,255,0.86)', backdropFilter: 'blur(18px) saturate(180%)', WebkitBackdropFilter: 'blur(18px) saturate(180%)' }}
      >
        {LEFT.map(({ label, icon, path }) => tab(label, icon, path))}

        {/* Centre FAB */}
        <div
          className="flex flex-col items-center gap-1 flex-1 text-[10.5px] font-semibold"
          style={{ marginTop: -34 }}
        >
          {/* Inner relative wrapper so bottom-full anchors to the button top */}
          <div className="relative">

            {/* Speed-dial items — positioned above the FAB button */}
            {fabOpen && (
              <div className="absolute bottom-full mb-3 left-1/2 -translate-x-1/2 flex flex-col items-end gap-3 z-30">
                {menuItems.map((item, i) => (
                  <button
                    key={i}
                    onClick={item.action}
                    className="flex items-center gap-2 group"
                  >
                    <span
                      className="text-[12px] font-semibold text-[var(--color-text)] bg-white/95 rounded-xl px-3 py-1.5 border border-[var(--color-border)] whitespace-nowrap group-hover:bg-[var(--color-bg)] transition-colors"
                      style={{ boxShadow: '0 2px 8px rgba(0,0,0,.08)' }}
                    >
                      {item.label}
                    </span>
                    <div
                      className={`w-[44px] h-[44px] rounded-full flex items-center justify-center shrink-0 ${
                        item.accent
                          ? 'bg-[var(--color-accent)]'
                          : 'bg-[var(--color-surface)] border border-[var(--color-border)]'
                      }`}
                      style={{ boxShadow: item.accent ? 'color-mix(in srgb, var(--color-accent) 35%, transparent) 0 4px 14px' : '0 2px 8px rgba(0,0,0,.08)' }}
                    >
                      <item.Icon
                        size={19}
                        strokeWidth={2.2}
                        color={item.accent ? '#fff' : undefined}
                        className={item.accent ? '' : 'text-[var(--color-text)]'}
                      />
                    </div>
                  </button>
                ))}
              </div>
            )}

            {/* FAB button */}
            <button
              onClick={() => setFabOpen(v => !v)}
              className="w-[52px] h-[52px] rounded-full bg-[var(--color-accent)] flex items-center justify-center focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-[var(--color-accent)]"
              style={{ boxShadow: 'color-mix(in srgb, var(--color-accent) 42%, transparent) 0 8px 20px' }}
              aria-label={fabOpen ? 'Close menu' : 'Open workout menu'}
            >
              <Plus
                size={26}
                strokeWidth={2.4}
                color="#fff"
                style={{ transform: fabOpen ? 'rotate(45deg)' : 'rotate(0deg)', transition: 'transform 0.2s ease' }}
              />
            </button>
          </div>

          <span className={active && !fabOpen ? 'text-[var(--color-accent)]' : 'text-[var(--color-faint)]'}>
            {fabOpen ? ' ' : active ? 'Resume' : 'Start'}
          </span>
        </div>

        {RIGHT.map(({ label, icon, path }) => tab(label, icon, path))}
      </nav>
    </>
  )
}

import { NavLink } from 'react-router-dom'
import { Settings } from 'lucide-react'
import Sidebar from './Sidebar'
import BottomNav from './BottomNav'

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0 min-h-0">
        {/* Mobile-only settings access */}
        <div className="md:hidden flex justify-end px-4 py-3 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
          <NavLink to="/settings" className={({ isActive }) => isActive ? 'text-[var(--color-accent)]' : 'text-[var(--color-muted)]'}>
            <Settings size={20} />
          </NavLink>
        </div>
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
        <BottomNav />
      </div>
    </div>
  )
}

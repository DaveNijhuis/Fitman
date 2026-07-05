import Sidebar from './Sidebar'
import BottomNav from './BottomNav'

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-full">
      <Sidebar />
      <div className="flex flex-col flex-1 min-w-0 min-h-0">
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>
        <BottomNav />
      </div>
    </div>
  )
}

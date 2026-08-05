import { NavLink } from 'react-router-dom'
import { LayoutDashboard, ListChecks, PenSquare, Clock, Settings, Waypoints } from 'lucide-react'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/queue', label: 'Queue', icon: ListChecks },
  { to: '/manual', label: 'Manual Post', icon: PenSquare },
  { to: '/scheduler', label: 'Scheduler', icon: Clock },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function Sidebar() {
  return (
    <aside className="w-60 shrink-0 h-screen sticky top-0 flex flex-col border-r border-line bg-bg-surface/60">
      <div className="flex items-center gap-2.5 px-5 h-16 border-b border-line">
        <div className="w-8 h-8 rounded-lg bg-accent/15 border border-accent/30 flex items-center justify-center">
          <Waypoints size={16} className="text-accent" />
        </div>
        <div className="leading-tight">
          <p className="font-display font-semibold text-sm text-ink">Content Pipeline</p>
          <p className="text-[11px] text-ink-faint">LinkedIn Automation</p>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors relative ${
                isActive
                  ? 'bg-accent/10 text-accent font-medium'
                  : 'text-ink-muted hover:text-ink hover:bg-bg-raised'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-accent" />
                )}
                <Icon size={17} strokeWidth={2} />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="px-5 py-4 border-t border-line">
        <p className="text-[11px] text-ink-faint leading-relaxed">
          Runs locally. No auth. Talks to <span className="font-mono text-ink-muted">linkedin_bot.db</span>
        </p>
      </div>
    </aside>
  )
}

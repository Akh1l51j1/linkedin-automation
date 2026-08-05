import { useEffect, useState, useCallback } from 'react'
import { Clock3, ListTodo, CalendarClock, RefreshCw } from 'lucide-react'
import { api } from '../api'

export default function TopBar() {
  const [stats, setStats] = useState(null)
  const [schedule, setSchedule] = useState(null)
  const [spinning, setSpinning] = useState(false)

  const load = useCallback(async () => {
    try {
      const [s, sch] = await Promise.all([api.getStats(), api.getScheduleStatus()])
      setStats(s)
      setSchedule(sch)
    } catch {
      // TopBar fails quietly — pages below surface their own toasts on real actions
    }
  }, [])

  useEffect(() => {
    load()
    const interval = setInterval(load, 15000)
    return () => clearInterval(interval)
  }, [load])

  const refresh = async () => {
    setSpinning(true)
    await load()
    setTimeout(() => setSpinning(false), 400)
  }

  const nextRun = schedule?.jobs?.length
    ? schedule.jobs
        .filter((j) => j.next_run_time)
        .sort((a, b) => new Date(a.next_run_time) - new Date(b.next_run_time))[0]
    : null

  return (
    <header className="h-16 sticky top-0 z-10 flex items-center justify-between px-6 border-b border-line bg-bg/80 backdrop-blur">
      <div className="flex items-center gap-6 text-sm">
        <Pill icon={ListTodo} label="Pending" value={stats?.pending ?? '—'} tone="pending" />
        <Pill icon={Clock3} label="Posted this week" value={stats?.posted_this_week ?? '—'} tone="posted" />
        <Pill
          icon={CalendarClock}
          label="Next run"
          value={
            !schedule?.running
              ? 'Scheduler off'
              : nextRun
                ? new Date(nextRun.next_run_time).toLocaleString(undefined, {
                    weekday: 'short',
                    hour: '2-digit',
                    minute: '2-digit',
                  })
                : '—'
          }
          tone="teal"
        />
      </div>
      <button onClick={refresh} className="btn-ghost !px-2.5" title="Refresh stats">
        <RefreshCw size={15} className={spinning ? 'animate-spin' : ''} />
      </button>
    </header>
  )
}

function Pill({ icon: Icon, label, value, tone }) {
  const toneClass = {
    pending: 'text-status-pending',
    posted: 'text-status-posted',
    teal: 'text-teal',
  }[tone]

  return (
    <div className="flex items-center gap-2">
      <Icon size={15} className={toneClass} />
      <span className="text-ink-faint">{label}</span>
      <span className="font-mono font-medium text-ink">{value}</span>
    </div>
  )
}

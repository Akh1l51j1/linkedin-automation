import { useCallback, useEffect, useState } from 'react'
import { ListTodo, CheckCircle2, Send, XCircle, RefreshCw, Zap, Loader2 } from 'lucide-react'
import StatsCard from '../components/StatsCard'
import PipelineFlow from '../components/PipelineFlow'
import MiniCalendar from '../components/MiniCalendar'
import { StatusBadge } from '../components/PostCard'
import { api } from '../api'
import { useToast } from '../context/ToastContext'

export default function Dashboard() {
  const toast = useToast()
  const [stats, setStats] = useState(null)
  const [recent, setRecent] = useState([])
  const [schedule, setSchedule] = useState(null)
  const [fetching, setFetching] = useState(false)
  const [posting, setPosting] = useState(false)

  const load = useCallback(async () => {
    try {
      const [s, queue, sch] = await Promise.all([
        api.getStats(),
        api.getQueue(),
        api.getScheduleStatus(),
      ])
      setStats(s)
      setSchedule(sch)
      setRecent(buildActivity(queue))
    } catch (err) {
      toast.error(err.message)
    }
  }, [toast])

  useEffect(() => { load() }, [load])

  const handleFetch = async () => {
    setFetching(true)
    try {
      const res = await api.triggerFetch()
      toast.success(res.message)
      await load()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setFetching(false)
    }
  }

  const handlePostNow = async () => {
    setPosting(true)
    try {
      const res = await api.postNow()
      toast.success(res.message)
      await load()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setPosting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard label="Total queued" value={stats?.total_queued ?? '—'} icon={ListTodo} tone="ink" />
        <StatsCard label="Approved ready" value={stats?.approved_ready ?? '—'} icon={CheckCircle2} tone="approved" />
        <StatsCard label="Posted this week" value={stats?.posted_this_week ?? '—'} icon={Send} tone="posted" />
        <StatsCard label="Failed posts" value={stats?.failed ?? '—'} icon={XCircle} tone="failed" />
      </div>

      <PipelineFlow stats={stats} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 card p-5">
          <p className="label mb-3">Recent activity</p>
          {recent.length === 0 ? (
            <p className="text-sm text-ink-faint py-6 text-center">
              Nothing yet — fetch some content or write a manual post to get started.
            </p>
          ) : (
            <ul className="space-y-2.5">
              {recent.map((item, i) => (
                <li key={i} className="flex items-center gap-3 text-sm">
                  <StatusBadge status={item.status} />
                  <span className="text-ink-muted truncate flex-1">{item.label}</span>
                  <span className="text-ink-faint text-xs font-mono shrink-0">{item.when}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card p-5 space-y-2.5">
          <p className="label mb-1">Quick actions</p>
          <button onClick={handleFetch} disabled={fetching} className="btn-secondary w-full justify-start">
            {fetching ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
            Fetch New Content
          </button>
          <button onClick={handlePostNow} disabled={posting} className="btn-primary w-full justify-start">
            {posting ? <Loader2 size={15} className="animate-spin" /> : <Zap size={15} />}
            Post Now
          </button>
          <p className="text-xs text-ink-faint pt-1">
            Fetch pulls new arXiv papers + RSS posts and summarizes them. Post Now publishes the next
            approved item (or the oldest pending one, auto-approved).
          </p>
        </div>
      </div>

      <MiniCalendar postTimes={schedule?.post_times || []} schedulerRunning={schedule?.running} />
    </div>
  )
}

function buildActivity(queue) {
  const withDate = queue
    .map((p) => {
      const ts =
        p.status === 'posted' ? p.posted_at : p.created_at
      return { p, ts: ts ? new Date(ts) : null }
    })
    .filter((x) => x.ts)
    .sort((a, b) => b.ts - a.ts)
    .slice(0, 5)

  return withDate.map(({ p, ts }) => ({
    status: p.status,
    label:
      p.status === 'posted'
        ? `Posted #${p.id} — ${p.source_title || 'Untitled'}`
        : p.status === 'approved'
          ? `Approved #${p.id} — ${p.source_title || 'Untitled'}`
          : p.status === 'failed'
            ? `Failed #${p.id} — ${p.source_title || 'Untitled'}`
            : `Queued #${p.id} — ${p.source_title || 'Untitled'}`,
    when: ts.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
  }))
}

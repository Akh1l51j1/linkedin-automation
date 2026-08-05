import { useCallback, useEffect, useState } from 'react'
import { Play, Square, Clock, Globe2, Terminal, Loader2 } from 'lucide-react'
import { api } from '../api'
import { useToast } from '../context/ToastContext'

export default function SchedulerPage() {
  const toast = useToast()
  const [status, setStatus] = useState(null)
  const [toggling, setToggling] = useState(false)

  const load = useCallback(async () => {
    try {
      setStatus(await api.getScheduleStatus())
    } catch (err) {
      toast.error(err.message)
    }
  }, [toast])

  useEffect(() => {
    load()
    const interval = setInterval(load, 10000)
    return () => clearInterval(interval)
  }, [load])

  const toggle = async () => {
    setToggling(true)
    try {
      const res = await api.toggleScheduler(!status?.running)
      toast.success(res.message)
      await load()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setToggling(false)
    }
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="card p-5 flex items-center justify-between">
        <div>
          <p className="label mb-1">Scheduler</p>
          <p className="text-sm text-ink-muted">
            {status?.running ? 'Running — fetch and post jobs are active.' : 'Stopped — nothing runs automatically.'}
          </p>
        </div>
        <button
          onClick={toggle}
          disabled={toggling}
          className={status?.running ? 'btn-danger' : 'btn-primary'}
        >
          {toggling ? (
            <Loader2 size={15} className="animate-spin" />
          ) : status?.running ? (
            <Square size={15} />
          ) : (
            <Play size={15} />
          )}
          {status?.running ? 'Stop scheduler' : 'Start scheduler'}
        </button>
      </div>

      <div className="card p-5">
        <p className="label mb-3">Next scheduled runs</p>
        {status?.running && status?.jobs?.length ? (
          <ul className="space-y-2">
            {status.jobs.map((job) => (
              <li key={job.id} className="flex items-center justify-between text-sm">
                <span className="text-ink-muted font-mono">{job.id}</span>
                <span className="text-ink font-mono">
                  {job.next_run_time
                    ? new Date(job.next_run_time).toLocaleString(undefined, {
                        weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
                      })
                    : '—'}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-ink-faint">Start the scheduler to see upcoming runs.</p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="card p-5">
          <p className="label mb-2 flex items-center gap-1.5"><Clock size={12} /> Post time slots</p>
          <div className="flex flex-wrap gap-1.5">
            {(status?.post_times || []).map((t) => (
              <span key={t} className="badge bg-bg-raised text-ink font-mono">{t}</span>
            ))}
          </div>
          <p className="text-xs text-ink-faint mt-3">
            Set in <span className="font-mono text-ink-muted">POST_TIMES</span> in linkedin_bot.py. Editing slots from
            the dashboard isn't wired up yet — it needs a small backend endpoint to persist changes safely.
          </p>
        </div>
        <div className="card p-5">
          <p className="label mb-2 flex items-center gap-1.5"><Globe2 size={12} /> Timezone</p>
          <p className="text-sm font-mono text-ink">{status?.timezone || '—'}</p>
          <p className="text-xs text-ink-faint mt-3">
            Set in <span className="font-mono text-ink-muted">TIMEZONE</span> in linkedin_bot.py.
          </p>
        </div>
      </div>

      <div className="card p-5">
        <p className="label mb-2 flex items-center gap-1.5"><Terminal size={12} /> Logs</p>
        <p className="text-sm text-ink-faint leading-relaxed">
          The bot currently logs to stdout in the terminal running <span className="font-mono text-ink-muted">uvicorn</span>.
          A live log viewer here would need the backend to capture output to a ring buffer or file and expose it
          over a <span className="font-mono text-ink-muted">/api/logs</span> endpoint (or websocket) — worth adding
          as a follow-up if you want it in-app.
        </p>
      </div>
    </div>
  )
}

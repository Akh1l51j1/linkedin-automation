const DAY_LABEL = { weekday: 'short' }

export default function MiniCalendar({ postTimes = [], schedulerRunning }) {
  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date()
    d.setDate(d.getDate() + i)
    return d
  })

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-4">
        <p className="label">Next 7 days</p>
        {!schedulerRunning && (
          <span className="text-xs text-ink-faint">scheduler is off — slots shown are hypothetical</span>
        )}
      </div>
      <div className="grid grid-cols-7 gap-2">
        {days.map((d, i) => (
          <div
            key={i}
            className={`rounded-lg border p-2.5 text-center ${
              i === 0 ? 'border-accent/40 bg-accent/5' : 'border-line bg-bg-raised'
            }`}
          >
            <p className="text-[11px] text-ink-faint">{d.toLocaleDateString(undefined, DAY_LABEL)}</p>
            <p className="font-mono text-sm text-ink mt-0.5">{d.getDate()}</p>
            <div className="mt-2 space-y-1">
              {postTimes.map((t) => (
                <div
                  key={t}
                  className={`text-[10px] font-mono rounded px-1 py-0.5 ${
                    schedulerRunning
                      ? 'bg-status-posted/10 text-status-posted'
                      : 'bg-bg-surface text-ink-faint'
                  }`}
                >
                  {t}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

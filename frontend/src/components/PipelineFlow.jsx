const STAGES = [
  { key: 'pending', label: 'Pending', color: '#FBBF24' },
  { key: 'approved', label: 'Approved', color: '#34D399' },
  { key: 'posted', label: 'Posted', color: '#60A5FA' },
  { key: 'failed', label: 'Failed', color: '#F87171' },
]

/**
 * The signature visual for this dashboard: a horizontal flow showing how
 * content actually moves through the bot's pipeline (pending → approved →
 * posted), with failed content branching off. Widths are proportional to
 * count so the bar itself tells you where content is piling up.
 */
export default function PipelineFlow({ stats }) {
  const counts = {
    pending: stats?.pending ?? 0,
    approved: stats?.approved_ready ?? 0,
    posted: stats?.posted_this_week ?? 0,
    failed: stats?.failed ?? 0,
  }
  const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1

  return (
    <div className="card p-5">
      <div className="flex items-center justify-between mb-4">
        <p className="label">Pipeline flow</p>
        <p className="text-xs text-ink-faint">posted count reflects this week</p>
      </div>

      <div className="flex h-2.5 rounded-full overflow-hidden bg-bg-raised">
        {STAGES.map((s) => {
          const width = (counts[s.key] / total) * 100
          if (width === 0) return null
          return (
            <div
              key={s.key}
              style={{ width: `${width}%`, backgroundColor: s.color }}
              className="h-full first:rounded-l-full last:rounded-r-full transition-all duration-500"
            />
          )
        })}
      </div>

      <div className="flex items-center justify-between mt-4">
        {STAGES.map((s, i) => (
          <div key={s.key} className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }} />
            <span className="text-xs text-ink-muted">{s.label}</span>
            <span className="font-mono text-xs text-ink">{counts[s.key]}</span>
            {i < STAGES.length - 1 && <span className="text-ink-faint mx-1.5">→</span>}
          </div>
        ))}
      </div>
    </div>
  )
}

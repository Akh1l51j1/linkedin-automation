export default function StatsCard({ label, value, icon: Icon, tone = 'ink', hint }) {
  const toneClasses = {
    ink: 'text-ink bg-bg-raised',
    accent: 'text-accent bg-accent/10',
    pending: 'text-status-pending bg-status-pending/10',
    approved: 'text-status-approved bg-status-approved/10',
    posted: 'text-status-posted bg-status-posted/10',
    failed: 'text-status-failed bg-status-failed/10',
  }

  return (
    <div className="card p-5 flex items-start justify-between">
      <div>
        <p className="label mb-2">{label}</p>
        <p className="font-display text-3xl font-semibold text-ink tabular-nums">{value}</p>
        {hint && <p className="text-xs text-ink-faint mt-1.5">{hint}</p>}
      </div>
      {Icon && (
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${toneClasses[tone]}`}>
          <Icon size={17} />
        </div>
      )}
    </div>
  )
}

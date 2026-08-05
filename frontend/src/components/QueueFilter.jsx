import { Search, ArrowDownUp } from 'lucide-react'

const TABS = [
  { key: 'all', label: 'All' },
  { key: 'pending', label: 'Pending' },
  { key: 'approved', label: 'Approved' },
  { key: 'posted', label: 'Posted' },
  { key: 'failed', label: 'Failed' },
]

export default function QueueFilter({ active, onChange, search, onSearch, sortOrder, onSortToggle }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
      <div className="flex items-center gap-1 bg-bg-raised border border-line rounded-lg p-1 w-fit">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => onChange(t.key)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              active === t.key ? 'bg-accent text-bg' : 'text-ink-muted hover:text-ink'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2">
        <div className="relative">
          <Search size={15} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-faint" />
          <input
            value={search}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Search title or content…"
            className="input pl-8 w-64"
          />
        </div>
        <button onClick={onSortToggle} className="btn-secondary" title="Toggle sort order">
          <ArrowDownUp size={14} />
          {sortOrder === 'newest' ? 'Newest' : 'Oldest'}
        </button>
      </div>
    </div>
  )
}

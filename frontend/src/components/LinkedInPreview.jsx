import { useState } from 'react'
import { ThumbsUp, MessageCircle, Repeat2, Send, Waypoints } from 'lucide-react'

const SEE_MORE_CUTOFF = 140

function renderWithHashtags(text) {
  const parts = text.split(/(#[a-zA-Z0-9_]+)/g)
  return parts.map((part, i) =>
    part.startsWith('#') ? (
      <span key={i} className="text-teal">{part}</span>
    ) : (
      <span key={i}>{part}</span>
    )
  )
}

export default function LinkedInPreview({ content, title }) {
  const [expanded, setExpanded] = useState(false)
  const charCount = content.length
  const isLong = content.length > SEE_MORE_CUTOFF
  const visibleText = expanded || !isLong ? content : content.slice(0, SEE_MORE_CUTOFF)

  return (
    <div className="card p-0 overflow-hidden max-w-md">
      <div className="p-4 pb-3 flex items-center gap-3">
        <div className="w-11 h-11 rounded-full bg-accent/15 border border-accent/30 flex items-center justify-center shrink-0">
          <Waypoints size={18} className="text-accent" />
        </div>
        <div className="min-w-0">
          <p className="text-sm font-medium text-ink truncate">You</p>
          <p className="text-xs text-ink-faint">{title || 'Now'} · 🌐</p>
        </div>
      </div>

      <div className="px-4 pb-3">
        {content ? (
          <p className="text-sm text-ink whitespace-pre-line leading-relaxed">
            {renderWithHashtags(visibleText)}
            {isLong && !expanded && (
              <>
                …{' '}
                <button onClick={() => setExpanded(true)} className="text-ink-faint hover:text-ink font-medium">
                  see more
                </button>
              </>
            )}
          </p>
        ) : (
          <p className="text-sm text-ink-faint italic">Your post will preview here as you type…</p>
        )}
      </div>

      <div className="px-4 pb-3 flex items-center justify-between text-xs text-ink-faint">
        <span className={charCount > 3000 ? 'text-status-failed' : ''}>
          {charCount.toLocaleString()} / 3,000 characters
        </span>
        {isLong && <span>cuts at {SEE_MORE_CUTOFF} chars</span>}
      </div>

      <div className="border-t border-line px-2 py-1.5 flex items-center justify-around">
        {[
          { icon: ThumbsUp, label: 'Like' },
          { icon: MessageCircle, label: 'Comment' },
          { icon: Repeat2, label: 'Repost' },
          { icon: Send, label: 'Send' },
        ].map(({ icon: Icon, label }) => (
          <button key={label} className="flex items-center gap-1.5 text-ink-faint px-2 py-1.5 rounded hover:bg-bg-raised text-xs" disabled>
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>
    </div>
  )
}

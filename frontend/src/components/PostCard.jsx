import { useState } from 'react'
import { Eye, Check, Pencil, Send, Trash2, ExternalLink, X, Loader2, RefreshCw } from 'lucide-react'

export function StatusBadge({ status }) {
  const styles = {
    pending: 'bg-status-pending/10 text-status-pending',
    approved: 'bg-status-approved/10 text-status-approved',
    posted: 'bg-status-posted/10 text-status-posted',
    failed: 'bg-status-failed/10 text-status-failed',
  }
  return (
    <span className={`badge ${styles[status] || 'bg-bg-raised text-ink-muted'}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {status}
    </span>
  )
}

function firstTwoLines(content) {
  return content.split('\n').filter(Boolean).slice(0, 2).join('\n')
}

export default function PostCard({
  post,
  selected,
  onToggleSelect,
  onApprove,
  onDelete,
  onEdit,
  onPostNow,
  onResummarize,
}) {
  const [viewing, setViewing] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(post.content)
  const [busy, setBusy] = useState(null) // 'approve' | 'delete' | 'post' | 'save'

  const run = async (action, fn) => {
    setBusy(action)
    try {
      await fn()
    } finally {
      setBusy(null)
    }
  }

  const created = post.created_at
    ? new Date(post.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    : ''

  return (
    <>
      <div className="card p-4 flex flex-col gap-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-2.5 min-w-0">
            <input
              type="checkbox"
              checked={selected}
              onChange={onToggleSelect}
              className="mt-1 accent-accent shrink-0"
            />
            <div className="min-w-0">
              <p className="text-sm font-medium text-ink truncate">
                {post.source_title || 'Untitled'}
              </p>
              <p className="text-xs text-ink-faint font-mono mt-0.5">#{post.id} · {created}</p>
            </div>
          </div>
          <StatusBadge status={post.status} />
        </div>

        <p className="text-sm text-ink-muted whitespace-pre-line line-clamp-2">
          {firstTwoLines(post.content)}
        </p>

        <div className="flex items-center gap-1.5 pt-1 border-t border-line -mx-4 px-4 pt-3">
          <button onClick={() => setViewing(true)} className="btn-ghost !px-2 text-xs">
            <Eye size={13} /> View
          </button>

          {post.status === 'pending' && (
            <button
              onClick={() => run('approve', () => onApprove(post.id))}
              className="btn-ghost !px-2 text-xs text-status-approved hover:bg-status-approved/10"
              disabled={busy !== null}
            >
              {busy === 'approve' ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />} Approve
            </button>
          )}

          {post.status !== 'posted' && (
            <button onClick={() => { setDraft(post.content); setEditing(true) }} className="btn-ghost !px-2 text-xs">
              <Pencil size={13} /> Edit
            </button>
          )}

          {post.status !== 'posted' && (
            <button
              onClick={() => run('resummarize', () => onResummarize(post.id))}
              className="btn-ghost !px-2 text-xs text-teal hover:bg-teal/10"
              disabled={busy !== null}
              title="Re-run LLM summarization"
            >
              {busy === 'resummarize' ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />} Re-summarize
            </button>
          )}

          {post.status === 'approved' && (
            <button
              onClick={() => run('post', () => onPostNow(post.id))}
              className="btn-ghost !px-2 text-xs text-status-posted hover:bg-status-posted/10"
              disabled={busy !== null}
            >
              {busy === 'post' ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />} Post Now
            </button>
          )}

          <button
            onClick={() => run('delete', () => onDelete(post.id))}
            className="btn-ghost !px-2 text-xs text-status-failed hover:bg-status-failed/10 ml-auto"
            disabled={busy !== null}
          >
            {busy === 'delete' ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />} Delete
          </button>
        </div>
      </div>

      {/* View modal */}
      {viewing && (
        <Modal onClose={() => setViewing(false)} title={post.source_title || 'Untitled'}>
          <div className="flex items-center gap-2 mb-3">
            <StatusBadge status={post.status} />
            {post.source_url && (
              <a
                href={post.source_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-teal hover:underline flex items-center gap-1"
              >
                Source <ExternalLink size={11} />
              </a>
            )}
          </div>
          <p className="text-sm text-ink whitespace-pre-line leading-relaxed">{post.content}</p>
        </Modal>
      )}

      {/* Edit modal */}
      {editing && (
        <Modal onClose={() => setEditing(false)} title={`Edit #${post.id}`}>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={10}
            className="input font-mono text-sm resize-none"
          />
          <div className="flex justify-end gap-2 mt-3">
            <button onClick={() => setEditing(false)} className="btn-secondary text-sm">Cancel</button>
            <button
              onClick={async () => {
                await run('save', () => onEdit(post.id, draft))
                setEditing(false)
              }}
              className="btn-primary text-sm"
              disabled={busy !== null || !draft.trim()}
            >
              {busy === 'save' ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} Save changes
            </button>
          </div>
        </Modal>
      )}
    </>
  )
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className="card w-full max-w-lg max-h-[80vh] overflow-y-auto p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-3 gap-3">
          <h3 className="font-display font-semibold text-ink">{title}</h3>
          <button onClick={onClose} className="text-ink-faint hover:text-ink shrink-0">
            <X size={16} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

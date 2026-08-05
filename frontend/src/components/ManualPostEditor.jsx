import { Hash } from 'lucide-react'

const TEMPLATES = [
  '🚀 New project:',
  '📚 Paper breakdown:',
  '💡 Hot take:',
  '🔥 Thread:',
  '❓ Question for the community:',
]

const COMMON_HASHTAGS = ['#AI', '#MachineLearning', '#LLM', '#MLOps', '#DeepLearning']

export default function ManualPostEditor({
  content,
  onContentChange,
  title,
  onTitleChange,
  sourceUrl,
  onSourceUrlChange,
  status,
  onStatusChange,
}) {
  const insertSnippet = (snippet) => {
    const prefix = content ? `${content}\n\n` : ''
    onContentChange(`${prefix}${snippet} `)
  }

  const insertHashtag = (tag) => {
    if (content.includes(tag)) return
    const needsSpace = content && !content.endsWith(' ') && !content.endsWith('\n')
    onContentChange(`${content}${needsSpace ? ' ' : ''}${tag}`)
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="label mb-1.5 block">Post content</label>
        <textarea
          value={content}
          onChange={(e) => onContentChange(e.target.value)}
          rows={12}
          placeholder="Write your LinkedIn post…"
          className="input font-body text-sm resize-none leading-relaxed"
        />
      </div>

      <div>
        <p className="label mb-1.5">Templates</p>
        <div className="flex flex-wrap gap-1.5">
          {TEMPLATES.map((t) => (
            <button key={t} onClick={() => insertSnippet(t)} className="btn-secondary !py-1.5 !px-2.5 text-xs">
              {t}
            </button>
          ))}
        </div>
      </div>

      <div>
        <p className="label mb-1.5 flex items-center gap-1"><Hash size={11} /> Quick-add hashtags</p>
        <div className="flex flex-wrap gap-1.5">
          {COMMON_HASHTAGS.map((tag) => (
            <button
              key={tag}
              onClick={() => insertHashtag(tag)}
              disabled={content.includes(tag)}
              className="btn-ghost !py-1 !px-2.5 text-xs border border-line disabled:opacity-30"
            >
              {tag}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label mb-1.5 block">Title / tag (optional)</label>
          <input
            value={title}
            onChange={(e) => onTitleChange(e.target.value)}
            placeholder="My Take on Transformers"
            className="input text-sm"
          />
        </div>
        <div>
          <label className="label mb-1.5 block">Source URL (optional)</label>
          <input
            value={sourceUrl}
            onChange={(e) => onSourceUrlChange(e.target.value)}
            placeholder="https://…"
            className="input text-sm"
          />
        </div>
      </div>

      <div>
        <label className="label mb-1.5 block">Save as</label>
        <div className="flex items-center gap-1 bg-bg-raised border border-line rounded-lg p-1 w-fit">
          <button
            onClick={() => onStatusChange('pending')}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              status === 'pending' ? 'bg-status-pending text-bg' : 'text-ink-muted hover:text-ink'
            }`}
          >
            Pending — review later
          </button>
          <button
            onClick={() => onStatusChange('approved')}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              status === 'approved' ? 'bg-status-approved text-bg' : 'text-ink-muted hover:text-ink'
            }`}
          >
            Approved — ready to post
          </button>
        </div>
      </div>
    </div>
  )
}

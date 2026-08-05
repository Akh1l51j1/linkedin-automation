import { useEffect, useState } from 'react'
import { Eye, EyeOff, Plus, X, TriangleAlert, Loader2, Trash2, RotateCcw, Save } from 'lucide-react'
import { api } from '../api'
import { useToast } from '../context/ToastContext'

const KEY_FIELDS = [
  { key: 'GROQ_API_KEY', label: 'Groq API Key' },
  { key: 'GEMINI_API_KEY', label: 'Gemini API Key' },
  { key: 'OPENROUTER_API_KEY', label: 'OpenRouter API Key' },
  { key: 'LINKEDIN_ACCESS_TOKEN', label: 'LinkedIn Access Token' },
  { key: 'LINKEDIN_AUTHOR_URN', label: 'LinkedIn Author URN' },
]

const ALL_ARXIV_CATEGORIES = ['cs.LG', 'cs.CL', 'cs.AI', 'cs.CV', 'cs.RO', 'cs.HC', 'cs.NE', 'stat.ML']

function NotWiredNote({ children }) {
  return (
    <p className="text-xs text-ink-faint flex items-start gap-1.5 mt-3">
      <TriangleAlert size={12} className="shrink-0 mt-0.5 text-status-pending" />
      {children}
    </p>
  )
}

export default function SettingsPage() {
  const toast = useToast()

  // API key state
  const [keys, setKeys] = useState(Object.fromEntries(KEY_FIELDS.map((f) => [f.key, ''])))
  const [keyStatus, setKeyStatus] = useState({}) // { KEY: { masked, is_set } }
  const [showKeys, setShowKeys] = useState({})
  const [savingKeys, setSavingKeys] = useState(false)
  const [feeds, setFeeds] = useState([])
  const [newFeed, setNewFeed] = useState('')
  const [categories, setCategories] = useState([])
  const [prompt, setPrompt] = useState('')
  const [promptIsCustom, setPromptIsCustom] = useState(false)
  const [savingPrompt, setSavingPrompt] = useState(false)
  const [resettingPrompt, setResettingPrompt] = useState(false)
  const [savingSources, setSavingSources] = useState(false)

  // Danger zone — these ARE wired to real endpoints.
  const [queueCount, setQueueCount] = useState(null)
  const [clearing, setClearing] = useState(false)

  useEffect(() => {
    api.getQueue().then((q) => setQueueCount(q.length)).catch(() => {})
    // Load current key status from backend
    api.getKeys().then((data) => setKeyStatus(data)).catch(() => {})
    // Load the active prompt from backend
    api
      .getPrompt()
      .then(({ prompt: p, is_custom }) => {
        setPrompt(p)
        setPromptIsCustom(is_custom)
      })
      .catch(() => {})
    // Load sources
    api
      .getSources()
      .then(({ rss_feeds, arxiv_categories }) => {
        setFeeds(rss_feeds || [])
        setCategories(arxiv_categories || [])
      })
      .catch(() => {})
  }, [])

  const saveKeys = async () => {
    // Only send keys that the user actually typed something into
    const toSave = {}
    for (const { key } of KEY_FIELDS) {
      if (keys[key].trim()) {
        toSave[key] = keys[key].trim()
      }
    }
    if (Object.keys(toSave).length === 0) {
      toast.error('Enter at least one key to save.')
      return
    }
    setSavingKeys(true)
    try {
      const result = await api.saveKeys(toSave)
      toast.success(result.message)
      // Refresh status and clear inputs
      setKeys(Object.fromEntries(KEY_FIELDS.map((f) => [f.key, ''])))
      const updated = await api.getKeys()
      setKeyStatus(updated)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSavingKeys(false)
    }
  }

  const savePrompt = async () => {
    setSavingPrompt(true)
    try {
      const result = await api.savePrompt(prompt)
      toast.success(result.message)
      setPromptIsCustom(true)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSavingPrompt(false)
    }
  }

  const resetPrompt = async () => {
    if (!confirm('Reset the prompt to the built-in default? Your custom prompt will be deleted.')) return
    setResettingPrompt(true)
    try {
      const result = await api.resetPrompt()
      toast.success(result.message)
      const { prompt: p, is_custom } = await api.getPrompt()
      setPrompt(p)
      setPromptIsCustom(is_custom)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setResettingPrompt(false)
    }
  }

  const toggleCategory = (cat) => {
    setCategories((prev) => (prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]))
  }

  const removeFeed = (url) => setFeeds((prev) => prev.filter((f) => f !== url))
  const addFeed = () => {
    if (!newFeed.trim()) return
    setFeeds((prev) => [...prev, newFeed.trim()])
    setNewFeed('')
  }

  const saveSources = async () => {
    setSavingSources(true)
    try {
      const result = await api.saveSources(feeds, categories)
      toast.success(result.message)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSavingSources(false)
    }
  }

  const clearQueue = async () => {
    if (!confirm('Delete every item currently in the queue? This cannot be undone.')) return
    setClearing(true)
    try {
      const all = await api.getQueue()
      let ok = 0
      for (const post of all) {
        try {
          await api.rejectPost(post.id)
          ok++
        } catch {
          // best-effort, continue clearing the rest
        }
      }
      toast.success(`Cleared ${ok} post(s) from the queue.`)
      setQueueCount(0)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setClearing(false)
    }
  }

  return (
    <div className="max-w-3xl space-y-4">
      {/* API Keys */}
      <section className="card p-5">
        <p className="label mb-1">API keys</p>
        <p className="text-sm text-ink-faint mb-4">
          Enter your keys below and hit Save. Only filled fields will be updated.
        </p>
        <div className="space-y-3">
          {KEY_FIELDS.map(({ key, label }) => (
            <div key={key}>
              <label className="text-xs text-ink-muted mb-1 flex items-center gap-2">
                {label}
                {keyStatus[key]?.is_set && (
                  <span className="inline-flex items-center gap-1 text-[10px] text-status-approved font-medium">
                    <span className="w-1.5 h-1.5 rounded-full bg-status-approved inline-block" />
                    configured
                  </span>
                )}
              </label>
              <div className="relative">
                <input
                  type={showKeys[key] ? 'text' : 'password'}
                  value={keys[key]}
                  onChange={(e) => setKeys((prev) => ({ ...prev, [key]: e.target.value }))}
                  placeholder={keyStatus[key]?.is_set ? keyStatus[key].masked : `${key}=…`}
                  className="input font-mono text-sm pr-9"
                />
                <button
                  onClick={() => setShowKeys((prev) => ({ ...prev, [key]: !prev[key] }))}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-faint hover:text-ink"
                >
                  {showKeys[key] ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>
          ))}
        </div>
        <button onClick={saveKeys} disabled={savingKeys} className="btn-secondary mt-4">
          {savingKeys ? <Loader2 size={14} className="animate-spin" /> : null}
          Save to .env
        </button>
      </section>

      {/* RSS Feeds */}
      <section className="card p-5">
        <div className="flex items-center justify-between mb-3">
          <p className="label">RSS feeds</p>
          <button
            onClick={saveSources}
            disabled={savingSources}
            className="btn-secondary !py-1 !px-3 text-xs flex items-center gap-1"
          >
            {savingSources ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
            Save sources
          </button>
        </div>
        <div className="space-y-1.5">
          {feeds.map((url) => (
            <div key={url} className="flex items-center gap-2 bg-bg-raised border border-line rounded-lg px-3 py-2">
              <span className="text-sm font-mono text-ink-muted truncate flex-1">{url}</span>
              <button className="btn-ghost !py-1 !px-2 text-xs" disabled>Test</button>
              <button onClick={() => removeFeed(url)} className="text-ink-faint hover:text-status-failed">
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-2 mt-3">
          <input
            value={newFeed}
            onChange={(e) => setNewFeed(e.target.value)}
            placeholder="https://example.com/feed.xml"
            className="input text-sm"
          />
          <button onClick={addFeed} className="btn-secondary shrink-0"><Plus size={14} /> Add</button>
        </div>
      </section>

      {/* arXiv categories */}
      <section className="card p-5">
        <div className="flex items-center justify-between mb-3">
          <p className="label">arXiv categories</p>
          <button
            onClick={saveSources}
            disabled={savingSources}
            className="btn-secondary !py-1 !px-3 text-xs flex items-center gap-1"
          >
            {savingSources ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
            Save sources
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {ALL_ARXIV_CATEGORIES.map((cat) => (
            <label
              key={cat}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm cursor-pointer transition-colors ${
                categories.includes(cat)
                  ? 'border-accent/50 bg-accent/10 text-accent'
                  : 'border-line bg-bg-raised text-ink-muted'
              }`}
            >
              <input
                type="checkbox"
                checked={categories.includes(cat)}
                onChange={() => toggleCategory(cat)}
                className="accent-accent"
              />
              {cat}
            </label>
          ))}
        </div>
      </section>

      {/* LLM prompt editor */}
      <section className="card p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <p className="label">Summarization prompt</p>
            {promptIsCustom && (
              <span className="inline-flex items-center gap-1 text-[10px] text-accent font-medium px-2 py-0.5 rounded-full bg-accent/10 border border-accent/20">
                custom
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {promptIsCustom && (
              <button
                onClick={resetPrompt}
                disabled={resettingPrompt}
                className="btn-ghost !py-1 !px-2 text-xs flex items-center gap-1"
                title="Reset to built-in default"
              >
                {resettingPrompt ? <Loader2 size={12} className="animate-spin" /> : <RotateCcw size={12} />}
                Reset
              </button>
            )}
            <button
              onClick={savePrompt}
              disabled={savingPrompt}
              className="btn-secondary !py-1 !px-3 text-xs flex items-center gap-1"
            >
              {savingPrompt ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
              Save prompt
            </button>
          </div>
        </div>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={12}
          className="input font-mono text-xs resize-y"
        />
        <p className="text-xs text-ink-faint mt-2">
          Maps to <span className="font-mono">SYSTEM_PROMPT</span> in linkedin_bot.py. Saved to{' '}
          <span className="font-mono">.env</span> and applied immediately — no restart needed.
        </p>
      </section>

      {/* Danger zone — real, working actions */}
      <section className="card p-5 border-status-failed/30">
        <p className="label mb-1 text-status-failed">Danger zone</p>
        <p className="text-sm text-ink-faint mb-4">These actions are permanent.</p>

        <div className="flex items-center justify-between py-3 border-t border-line">
          <div>
            <p className="text-sm text-ink">Clear queue</p>
            <p className="text-xs text-ink-faint">
              Deletes every item in the queue ({queueCount ?? '…'} currently). Uses the real reject endpoint.
            </p>
          </div>
          <button onClick={clearQueue} disabled={clearing} className="btn-danger">
            {clearing ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />} Clear queue
          </button>
        </div>

        <div className="flex items-center justify-between py-3 border-t border-line">
          <div>
            <p className="text-sm text-ink">Reset database</p>
            <p className="text-xs text-ink-faint">Drops and recreates all tables.</p>
          </div>
          <button disabled className="btn-danger opacity-40 cursor-not-allowed">Reset database</button>
        </div>

        <div className="flex items-center justify-between py-3 border-t border-line">
          <div>
            <p className="text-sm text-ink">Clear posted URLs history</p>
            <p className="text-xs text-ink-faint">Wipes dedup history — previously posted items can be re-fetched.</p>
          </div>
          <button disabled className="btn-danger opacity-40 cursor-not-allowed">Clear history</button>
        </div>

        <NotWiredNote>
          "Reset database" and "Clear posted URLs" need two small, deliberately destructive endpoints that don't
          exist yet — kept disabled rather than faking them, since silently no-op'ing a delete button is worse than
          not having it.
        </NotWiredNote>
      </section>
    </div>
  )
}

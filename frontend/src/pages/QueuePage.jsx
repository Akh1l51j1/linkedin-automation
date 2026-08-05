import { useCallback, useEffect, useMemo, useState } from 'react'
import { CheckCheck, Trash2, Loader2 } from 'lucide-react'
import QueueFilter from '../components/QueueFilter'
import PostCard from '../components/PostCard'
import { api } from '../api'
import { useToast } from '../context/ToastContext'

export default function QueuePage() {
  const toast = useToast()
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [sortOrder, setSortOrder] = useState('newest')
  const [selected, setSelected] = useState(new Set())
  const [bulkBusy, setBulkBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const data = await api.getQueue()
      setPosts(data)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setLoading(false)
    }
  }, [toast])

  useEffect(() => { load() }, [load])

  const filtered = useMemo(() => {
    let list = filter === 'all' ? posts : posts.filter((p) => p.status === filter)
    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(
        (p) =>
          (p.source_title || '').toLowerCase().includes(q) ||
          p.content.toLowerCase().includes(q)
      )
    }
    list = [...list].sort((a, b) => {
      const diff = new Date(b.created_at || 0) - new Date(a.created_at || 0)
      return sortOrder === 'newest' ? diff : -diff
    })
    return list
  }, [posts, filter, search, sortOrder])

  const toggleSelect = (id) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const withAction = async (fn, successMsg) => {
    try {
      await fn()
      if (successMsg) toast.success(successMsg)
      await load()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const bulkApprove = async () => {
    setBulkBusy(true)
    const ids = [...selected].filter((id) => posts.find((p) => p.id === id)?.status === 'pending')
    let ok = 0
    for (const id of ids) {
      try {
        await api.approvePost(id)
        ok++
      } catch {
        // continue with the rest, report partial success below
      }
    }
    toast.success(`Approved ${ok} of ${ids.length} selected post(s).`)
    setSelected(new Set())
    setBulkBusy(false)
    await load()
  }

  const bulkDelete = async () => {
    setBulkBusy(true)
    const ids = [...selected]
    let ok = 0
    for (const id of ids) {
      try {
        await api.rejectPost(id)
        ok++
      } catch {
        // continue with the rest, report partial success below
      }
    }
    toast.success(`Deleted ${ok} of ${ids.length} selected post(s).`)
    setSelected(new Set())
    setBulkBusy(false)
    await load()
  }

  return (
    <div className="space-y-4">
      <QueueFilter
        active={filter}
        onChange={setFilter}
        search={search}
        onSearch={setSearch}
        sortOrder={sortOrder}
        onSortToggle={() => setSortOrder((o) => (o === 'newest' ? 'oldest' : 'newest'))}
      />

      {selected.size > 0 && (
        <div className="card px-4 py-2.5 flex items-center justify-between">
          <p className="text-sm text-ink-muted">{selected.size} selected</p>
          <div className="flex items-center gap-2">
            <button onClick={bulkApprove} disabled={bulkBusy} className="btn-secondary text-xs !py-1.5">
              {bulkBusy ? <Loader2 size={13} className="animate-spin" /> : <CheckCheck size={13} />} Approve All
            </button>
            <button onClick={bulkDelete} disabled={bulkBusy} className="btn-danger text-xs !py-1.5">
              {bulkBusy ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />} Delete All
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="card p-4 h-36 animate-pulse bg-bg-raised/40" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="card p-10 text-center">
          <p className="text-sm text-ink-faint">
            {posts.length === 0
              ? 'Queue is empty. Fetch new content or write a manual post to get started.'
              : 'No posts match this filter or search.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((post) => (
            <PostCard
              key={post.id}
              post={post}
              selected={selected.has(post.id)}
              onToggleSelect={() => toggleSelect(post.id)}
              onApprove={(id) => withAction(() => api.approvePost(id), `Post #${id} approved.`)}
              onDelete={(id) => withAction(() => api.rejectPost(id), `Post #${id} deleted.`)}
              onEdit={(id, content) => withAction(() => api.editPost(id, content), `Post #${id} updated.`)}
              onPostNow={(id) => withAction(() => api.forcePost(id), `Post #${id} published.`)}
              onResummarize={(id) => withAction(() => api.resummarize(id), `Post #${id} re-summarized.`)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

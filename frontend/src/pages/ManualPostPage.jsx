import { useState } from 'react'
import { PlusCircle, Send, Loader2 } from 'lucide-react'
import ManualPostEditor from '../components/ManualPostEditor'
import LinkedInPreview from '../components/LinkedInPreview'
import { api } from '../api'
import { useToast } from '../context/ToastContext'

export default function ManualPostPage() {
  const toast = useToast()
  const [content, setContent] = useState('')
  const [title, setTitle] = useState('')
  const [sourceUrl, setSourceUrl] = useState('')
  const [status, setStatus] = useState('pending')
  const [savingQueue, setSavingQueue] = useState(false)
  const [savingPost, setSavingPost] = useState(false)

  const reset = () => {
    setContent('')
    setTitle('')
    setSourceUrl('')
    setStatus('pending')
  }

  const payload = () => ({
    content: content.trim(),
    source_title: title.trim() || undefined,
    source_url: sourceUrl.trim() || undefined,
    status,
  })

  const addToQueue = async () => {
    if (!content.trim()) return toast.error('Write some content first.')
    setSavingQueue(true)
    try {
      const res = await api.createManualPost(payload())
      toast.success(res.message)
      reset()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSavingQueue(false)
    }
  }

  const postImmediately = async () => {
    if (!content.trim()) return toast.error('Write some content first.')
    setSavingPost(true)
    try {
      const created = await api.createManualPost({ ...payload(), status: 'approved' })
      const newId = created?.data?.post?.id
      if (!newId) throw new Error('Post was queued but no ID was returned — check the Queue page.')
      const posted = await api.forcePost(newId)
      toast.success(posted.message)
      reset()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setSavingPost(false)
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6 items-start">
      <div className="card p-5 space-y-5">
        <ManualPostEditor
          content={content}
          onContentChange={setContent}
          title={title}
          onTitleChange={setTitle}
          sourceUrl={sourceUrl}
          onSourceUrlChange={setSourceUrl}
          status={status}
          onStatusChange={setStatus}
        />

        <div className="flex items-center gap-2 pt-2 border-t border-line">
          <button
            onClick={addToQueue}
            disabled={savingQueue || savingPost || !content.trim()}
            className="btn-secondary"
          >
            {savingQueue ? <Loader2 size={15} className="animate-spin" /> : <PlusCircle size={15} />}
            Add to Queue
          </button>
          <button
            onClick={postImmediately}
            disabled={savingQueue || savingPost || !content.trim()}
            className="btn-primary"
          >
            {savingPost ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
            Post Immediately
          </button>
        </div>
      </div>

      <div className="lg:sticky lg:top-20">
        <p className="label mb-2 px-1">Live preview</p>
        <LinkedInPreview content={content} title={title} />
      </div>
    </div>
  )
}

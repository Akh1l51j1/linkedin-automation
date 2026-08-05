import { createContext, useCallback, useContext, useState } from 'react'
import { CheckCircle2, XCircle, Info, X } from 'lucide-react'

const ToastContext = createContext(null)

let idCounter = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const push = useCallback((message, type = 'info') => {
    const id = ++idCounter
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => dismiss(id), 4500)
  }, [dismiss])

  const toast = {
    success: (msg) => push(msg, 'success'),
    error: (msg) => push(msg, 'error'),
    info: (msg) => push(msg, 'info'),
  }

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 w-80">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="card flex items-start gap-2.5 px-4 py-3 animate-[fadeIn_0.15s_ease-out]"
          >
            {t.type === 'success' && <CheckCircle2 size={18} className="text-status-approved shrink-0 mt-0.5" />}
            {t.type === 'error' && <XCircle size={18} className="text-status-failed shrink-0 mt-0.5" />}
            {t.type === 'info' && <Info size={18} className="text-teal shrink-0 mt-0.5" />}
            <p className="text-sm text-ink flex-1 leading-snug">{t.message}</p>
            <button onClick={() => dismiss(t.id)} className="text-ink-faint hover:text-ink shrink-0">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within a ToastProvider')
  return ctx
}

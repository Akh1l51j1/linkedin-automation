const BASE_URL = 'http://localhost:8000'

class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

async function request(path, options = {}) {
  let res
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch (err) {
    throw new ApiError('Cannot reach the backend. Is api.py running on port 8000?', 0)
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {
      // response wasn't JSON — keep default message
    }
    throw new ApiError(detail, res.status)
  }

  if (res.status === 204) return null
  return res.json()
}

export const api = {
  // Queue
  getQueue: (status) => request(`/api/queue${status ? `?status=${status}` : ''}`),
  getQueueItem: (id) => request(`/api/queue/${id}`),
  approvePost: (id) => request(`/api/queue/${id}/approve`, { method: 'POST' }),
  rejectPost: (id) => request(`/api/queue/${id}/reject`, { method: 'POST' }),
  editPost: (id, content) =>
    request(`/api/queue/${id}/edit`, { method: 'POST', body: JSON.stringify({ content }) }),
  resummarize: (id) =>
    request(`/api/queue/${id}/resummarize`, { method: 'POST' }),

  // Fetch & publish
  triggerFetch: () => request('/api/fetch', { method: 'POST' }),
  postNow: () => request('/api/post-now', { method: 'POST' }),
  forcePost: (id) => request(`/api/post/${id}`, { method: 'POST' }),

  // Manual post
  createManualPost: (payload) =>
    request('/api/manual-post', { method: 'POST', body: JSON.stringify(payload) }),

  // Scheduler
  toggleScheduler: (enable) =>
    request('/api/schedule/toggle', { method: 'POST', body: JSON.stringify({ enable }) }),
  getScheduleStatus: () => request('/api/schedule/status'),

  // Stats
  getStats: () => request('/api/stats'),

  // Settings
  getKeys: () => request('/api/settings/keys'),
  saveKeys: (keys) =>
    request('/api/settings/keys', { method: 'PUT', body: JSON.stringify({ keys }) }),

  // Prompt
  getPrompt: () => request('/api/settings/prompt'),
  savePrompt: (prompt) =>
    request('/api/settings/prompt', { method: 'PUT', body: JSON.stringify({ prompt }) }),
  resetPrompt: () => request('/api/settings/prompt', { method: 'DELETE' }),

  // Sources
  getSources: () => request('/api/settings/sources'),
  saveSources: (rss_feeds, arxiv_categories) =>
    request('/api/settings/sources', { method: 'PUT', body: JSON.stringify({ rss_feeds, arxiv_categories }) }),
}

export { ApiError }

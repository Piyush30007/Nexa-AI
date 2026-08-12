const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(options.headers || {}),
    },
  })

  if (!res.ok) {
    let detail = `Request failed with status ${res.status}`

    try {
      const body = await res.json()
      detail = body.detail || body.message || JSON.stringify(body)
    } catch {
      // Keep default error message.
    }

    throw new Error(detail)
  }

  if (res.status === 204) return null

  return res.json()
}

export const api = {
  health: () => request('/health'),

  uploadDocument: (file) => {
    const form = new FormData()
    form.append('file', file)

    return request('/api/documents/upload', {
      method: 'POST',
      body: form,
    })
  },

  chat: (question, conversationId = null) =>
    request('/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        question,
        conversation_id: conversationId,
      }),
    }),

  runEvaluation: () =>
    request('/api/evaluation/run', {
      method: 'POST',
    }),

  getEvaluationResults: () =>
    request('/api/evaluation/results'),
}
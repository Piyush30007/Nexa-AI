import { getToken } from '@clerk/react'

const BASE_URL =
  (typeof import.meta !== 'undefined' && import.meta.env && (import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL)) ||
  'http://localhost:8000'

let customTokenGetter = null

/**
 * Configure an optional custom token getter (used for testing or custom overrides).
 */
export function setAuthTokenGetter(fn) {
  customTokenGetter = fn
}

/**
 * Safely resolves the current Clerk session token.
 * Returns the JWT token string if signed in, or null for guest requests.
 * Throws a clear error if token retrieval fails for an active session.
 */
async function resolveClerkToken() {
  try {
    if (customTokenGetter) {
      return await customTokenGetter()
    }

    if (typeof window === 'undefined') {
      return null
    }

    const token = await getToken()
    return token || null
  } catch (err) {
    throw new Error(`Authentication token retrieval failed: ${err.message || err}`)
  }
}

async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData

  // 1. Resolve Clerk session token for authenticated users
  const token = await resolveClerkToken()
  const authHeaders = token ? { Authorization: `Bearer ${token}` } : {}

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...authHeaders,
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

  getDocuments: () =>
    request('/api/documents'),

  deleteDocument: (documentId) =>
    request(`/api/documents/${documentId}`, {
      method: 'DELETE',
    }),

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

  getConversations: () =>
    request('/api/conversations'),

  getConversationMessages: (conversationId) =>
    request(`/api/conversations/${conversationId}/messages`),

  deleteConversation: (conversationId) =>
    request(`/api/conversations/${conversationId}`, {
      method: 'DELETE',
    }),

  renameConversation: (conversationId, title) =>
    request(`/api/conversations/${conversationId}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    }),
}
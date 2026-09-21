import React, { useRef, useState, useEffect } from 'react'
import { useAuth } from '@clerk/react'
import { Card, Button, Badge, Spinner, MetricCard } from '../components/ui.jsx'
import AgentExecutionPanel from '../components/AgentExecutionPanel.jsx'
import SourceReceipt from '../components/SourceReceipt.jsx'
import {
  NexaLogo,
  PlusIcon,
  TrashIcon,
  SendIcon,
  PaperclipIcon,
  SlidersIcon,
  CheckCircleFilled,
  FileTextIcon,
  UsersIcon,
  CalendarIcon,
  ShieldIcon,
  BoltIcon,
  DatabaseIcon,
  AssistantIcon,
  CopyIcon,
  CheckIcon,
  ChevronDownIcon,
  XIcon,
  EditIcon,
} from '../components/Icons.jsx'
import { api } from '../api/client.js'

const SUGGESTIONS = [
  {
    category: 'Company Policies',
    question: 'What is the normal workweek for employees?',
    icon: FileTextIcon,
    color: 'blue',
  },
  {
    category: 'Benefits',
    question: 'What health insurance benefits are available?',
    icon: UsersIcon,
    color: 'orange',
  },
  {
    category: 'Leave Policy',
    question: 'How long is the unpaid lunch period during a normal workday?',
    icon: CalendarIcon,
    color: 'blue',
  },
  {
    category: 'Security',
    question: 'What are the company security guidelines?',
    icon: ShieldIcon,
    color: 'purple',
  },
]

// Helper to format assistant answer text with bolding and blue checkmark bullets
function FormattedAnswer({ text }) {
  if (!text) return null

  const lines = text.split('\n')
  return (
    <div className="space-y-2.5 text-sm text-slate-800 leading-relaxed font-sans">
      {lines.map((line, idx) => {
        const trimmed = line.trim()
        if (!trimmed) return <div key={idx} className="h-1.5" />

        // Check if line is a bullet item starting with -, *, or number
        const isBullet = trimmed.startsWith('- ') || trimmed.startsWith('* ') || /^\d+\.\s/.test(trimmed)
        const bulletText = isBullet ? trimmed.replace(/^[-*]\s+|\d+\.\s+/, '') : trimmed

        // Format **bold** segments
        const formatBold = (str) => {
          const parts = str.split(/(\*\*[^*]+\*\*)/g)
          return parts.map((part, pIdx) => {
            if (part.startsWith('**') && part.endsWith('**')) {
              return (
                <strong key={pIdx} className="font-semibold text-slate-900">
                  {part.slice(2, -2)}
                </strong>
              )
            }
            return part
          })
        }

        if (isBullet) {
          return (
            <div key={idx} className="flex items-start gap-2.5 pl-1 my-1">
              <CheckCircleFilled className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
              <div className="flex-1 text-slate-800">{formatBold(bulletText)}</div>
            </div>
          )
        }

        if (trimmed.endsWith(':') || trimmed.toLowerCase() === 'key points:') {
          return (
            <div key={idx} className="font-semibold text-slate-900 pt-1">
              {formatBold(trimmed)}
            </div>
          )
        }

        return <p key={idx}>{formatBold(line)}</p>
      })}
    </div>
  )
}

// Helper to format ISO timestamp into compact date/time (e.g. "Today, 2:30 PM", "Yesterday, 4:15 PM", "Sep 19, 2:30 PM")
function formatCompactDate(isoStr) {
  if (!isoStr) return ''
  try {
    let raw = String(isoStr).trim()
    if (!raw) return ''
    if (raw.includes(' ') && !raw.includes('T')) {
      raw = raw.replace(' ', 'T')
    }
    // If the ISO string lacks timezone information (e.g. "2026-09-21T01:40:15"),
    // treat it as UTC so the browser accurately converts it to local user time.
    const hasTz = raw.endsWith('Z') || /[+-]\d{2}(:\d{2})?$/.test(raw)
    const d = new Date(hasTz ? raw : `${raw}Z`)
    if (isNaN(d.getTime())) return ''
    const now = new Date()
    const isToday =
      d.getDate() === now.getDate() &&
      d.getMonth() === now.getMonth() &&
      d.getFullYear() === now.getFullYear()

    const yesterday = new Date(now)
    yesterday.setDate(now.getDate() - 1)
    const isYesterday =
      d.getDate() === yesterday.getDate() &&
      d.getMonth() === yesterday.getMonth() &&
      d.getFullYear() === yesterday.getFullYear()

    const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

    if (isToday) return `Today, ${timeStr}`
    if (isYesterday) return `Yesterday, ${timeStr}`
    const monthStr = d.toLocaleDateString([], { month: 'short', day: 'numeric' })
    return `${monthStr}, ${timeStr}`
  } catch {
    return String(isoStr).slice(0, 10)
  }
}

export default function AIAssistant() {
  const { isLoaded, isSignedIn, userId } = useAuth()

  // Authenticated conversation history state (Phase 7.1 & 7.2)
  const [conversations, setConversations] = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState(null)
  const [historyOpen, setHistoryOpen] = useState(true)
  const [selectedLoadingId, setSelectedLoadingId] = useState(null)
  const [deletingId, setDeletingId] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  const [renamingId, setRenamingId] = useState(null)
  const renameInputRef = useRef(null)

  const [messages, setMessages] = useState(() => {
    try {
      const saved = sessionStorage.getItem('nexa_messages')
      return saved ? JSON.parse(saved) : []
    } catch {
      return []
    }
  })

  const [input, setInput] = useState('')
  const [conversationId, setConversationId] = useState(() => {
    return sessionStorage.getItem('nexa_conversation_id') || null
  })

  const [loading, setLoading] = useState(false)
  const [copiedIndex, setCopiedIndex] = useState(null)
  const [advancedMode, setAdvancedMode] = useState(false)
  const [error, setError] = useState(null)

  const bottomRef = useRef(null)
  const inputRef = useRef(null)
  const fileInputRef = useRef(null)
  const prevAuthRef = useRef({ isLoaded: false, isSignedIn: false, userId: null })

  // Authenticated conversation history synchronization & auth transitions
  useEffect(() => {
    if (!isLoaded) return

    const prev = prevAuthRef.current

    // Case 1: Guest signs in -> safely reset guest chat state so it is not attached to user
    if (
      (prev.isLoaded && !prev.isSignedIn && isSignedIn) ||
      (isSignedIn && typeof window !== 'undefined' && sessionStorage.getItem('nexa_is_guest') === 'true')
    ) {
      setMessages([])
      setConversationId(null)
      try {
        sessionStorage.removeItem('nexa_messages')
        sessionStorage.removeItem('nexa_conversation_id')
        sessionStorage.removeItem('nexa_is_guest')
      } catch (e) {
        console.error('Failed to clear guest session:', e)
      }
    }

    // Case 2: User signs out -> clear authenticated history and active chat state
    if (prev.isLoaded && prev.isSignedIn && !isSignedIn) {
      setMessages([])
      setConversationId(null)
      setConversations([])
      setHistoryLoading(false)
      setHistoryError(null)
      try {
        sessionStorage.removeItem('nexa_messages')
        sessionStorage.removeItem('nexa_conversation_id')
        sessionStorage.removeItem('nexa_is_guest')
      } catch (e) {
        console.error('Failed to clear user session:', e)
      }
    }

    // Update previous auth state ref
    prevAuthRef.current = { isLoaded, isSignedIn, userId }

    // Fetch conversation history ONLY when authenticated
    if (isSignedIn) {
      let isMounted = true
      setHistoryLoading(true)
      setHistoryError(null)

      api
        .getConversations()
        .then((data) => {
          if (isMounted) {
            setConversations(Array.isArray(data) ? data : [])
            setHistoryLoading(false)
          }
        })
        .catch((err) => {
          if (isMounted) {
            setConversations([])
            setHistoryLoading(false)
            const msg = err.message || 'Failed to load conversation history.'
            setHistoryError(msg.includes('401') ? 'Session expired. Please sign in again.' : msg)
          }
        })

      return () => {
        isMounted = false
      }
    } else {
      // Guests: strictly do NOT call /api/conversations, clear history state
      setConversations([])
      setHistoryLoading(false)
      setHistoryError(null)
    }
  }, [isLoaded, isSignedIn, userId])

  // Persist session messages
  useEffect(() => {
    try {
      sessionStorage.setItem('nexa_messages', JSON.stringify(messages))
      if (!isSignedIn) {
        sessionStorage.setItem('nexa_is_guest', 'true')
      } else {
        sessionStorage.removeItem('nexa_is_guest')
      }
    } catch (e) {
      console.error('Failed to save messages:', e)
    }
  }, [messages, isSignedIn])

  // Persist session conversation ID
  useEffect(() => {
    try {
      if (conversationId) {
        sessionStorage.setItem('nexa_conversation_id', conversationId)
      } else {
        sessionStorage.removeItem('nexa_conversation_id')
      }
    } catch (e) {
      console.error('Failed to save conversation ID:', e)
    }
  }, [conversationId])

  const [docCount, setDocCount] = useState(null)

  // Load real document count from server (data integrity)
  useEffect(() => {
    let isMounted = true
    api
      .getDocuments()
      .then((serverDocs) => {
        if (isMounted && Array.isArray(serverDocs)) {
          setDocCount(serverDocs.length)
        }
      })
      .catch(() => {
        if (isMounted) setDocCount(null)
      })
    return () => {
      isMounted = false
    }
  }, [])

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Calculate session stats for bottom overview
  const totalQueries = messages.filter((m) => m.role === 'user').length
  const latencies = messages
    .filter((m) => m.role === 'assistant' && m.latency != null)
    .map((m) => Number(m.latency))
  const avgLatency =
    latencies.length > 0
      ? (latencies.reduce((a, b) => a + b, 0) / latencies.length / 1000).toFixed(2) + 's'
      : '—'

  const assistantMsgs = messages.filter((m) => m.role === 'assistant')
  const cacheHits = assistantMsgs.filter(
    (m) =>
      m.thoughtProcess?.some((t) => typeof t === 'string' && t.toLowerCase().includes('cache hit')) ||
      m.cached
  ).length
  const cacheHitRate =
    assistantMsgs.length > 0
      ? `${Math.round((cacheHits / assistantMsgs.length) * 100)}%`
      : '—'

  // Latest assistant message for right-hand execution & sources panel
  const latestAssistantMsg = [...messages].reverse().find((m) => m.role === 'assistant')
  const latestSources = latestAssistantMsg?.sources || []
  const latestLatency = latestAssistantMsg?.latency || null
  const latestGrounded = latestAssistantMsg?.grounded ?? true
  const latestThoughtProcess = latestAssistantMsg?.thoughtProcess || []
  const latestQuery = [...messages].reverse().find((m) => m.role === 'user')?.content || ''

  async function send(questionText) {
    const q = (questionText ?? input).trim()
    if (!q || loading) return

    setInput('')
    setError(null)

    const now = new Date()
    const timeStr = formatCompactDate(now.toISOString())

    // Add user message
    setMessages((prev) => [
      ...prev,
      {
        role: 'user',
        content: q,
        timestamp: timeStr,
      },
    ])

    setLoading(true)

    try {
      const response = await api.chat(q, conversationId)

      const newConvId = response.conversation_id || null
      setConversationId(newConvId)

      // If an authenticated user just initiated a new conversation, refresh the history list
      if (isSignedIn && !conversationId && newConvId) {
        api
          .getConversations()
          .then((data) => {
            setConversations(Array.isArray(data) ? data : [])
          })
          .catch(() => {})
      }

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: response.answer || 'No response generated.',
          sources: response.sources || [],
          grounded: response.grounded ?? false,
          latency: response.latency_ms,
          thoughtProcess: response.thought_process || [],
          status: response.status || 'completed',
          timestamp: formatCompactDate(new Date().toISOString()),
        },
      ])
    } catch (err) {
      console.error('Chat error:', err)
      setError(err.message || 'Something went wrong.')
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'I was unable to process your question. Please verify the backend connection and try again.',
          sources: [],
          grounded: false,
          timestamp: formatCompactDate(new Date().toISOString()),
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  // Select a conversation from history and load its messages
  async function handleSelectConversation(convId) {
    if (convId === conversationId || selectedLoadingId) return

    setSelectedLoadingId(convId)
    setError(null)

    try {
      const msgs = await api.getConversationMessages(convId)

      const formatted = (msgs || []).map((m) => {
        if (m.role === 'user') {
          return {
            id: m.id,
            role: 'user',
            content: m.content,
            timestamp: formatCompactDate(m.created_at),
          }
        }
        const sources = Array.isArray(m.sources) ? m.sources : []
        return {
          id: m.id,
          role: 'assistant',
          content: m.content,
          sources: sources,
          grounded: sources.length > 0,
          status: 'completed',
          timestamp: formatCompactDate(m.created_at),
        }
      })

      setMessages(formatted)
      setConversationId(convId)
    } catch (err) {
      console.error('Failed to load conversation messages:', err)
      setError(err.message || 'Failed to load conversation messages.')
    } finally {
      setSelectedLoadingId(null)
    }
  }

  // Delete a conversation from history
  async function handleDeleteConversation(convId, e) {
    if (e) e.stopPropagation()
    if (deletingId) return

    setDeletingId(convId)
    setError(null)

    try {
      await api.deleteConversation(convId)

      // Remove from state
      setConversations((prev) => prev.filter((c) => c.id !== convId))

      // If deleting the active conversation, clear active chat state
      if (convId === conversationId) {
        startNewConversation()
      }
    } catch (err) {
      console.error('Failed to delete conversation:', err)
      setError(err.message || 'Failed to delete conversation.')
    } finally {
      setDeletingId(null)
    }
  }

  function handleStartRename(conv, e) {
    if (e) e.stopPropagation()
    setEditingId(conv.id)
    setEditTitle(conv.title || '')
    setTimeout(() => renameInputRef.current?.focus(), 30)
  }

  function handleCancelRename(e) {
    if (e) e.stopPropagation()
    setEditingId(null)
    setEditTitle('')
  }

  async function handleSaveRename(convId, e) {
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    const trimmed = editTitle.trim()
    if (!trimmed || renamingId) return

    setRenamingId(convId)
    setError(null)

    try {
      const res = await api.renameConversation(convId, trimmed)
      const newTitle = res?.title || trimmed
      setConversations((prev) =>
        prev.map((c) => (c.id === convId ? { ...c, title: newTitle } : c))
      )
      setEditingId(null)
      setEditTitle('')
    } catch (err) {
      console.error('Failed to rename conversation:', err)
      setHistoryError(err.message || 'Failed to rename conversation.')
    } finally {
      setRenamingId(null)
    }
  }

  function startNewConversation() {
    setMessages([])
    setConversationId(null)
    setInput('')
    setError(null)
    sessionStorage.removeItem('nexa_messages')
    sessionStorage.removeItem('nexa_conversation_id')
    inputRef.current?.focus()
  }

  function handleCopy(text, idx) {
    navigator.clipboard?.writeText(text)
    setCopiedIndex(idx)
    setTimeout(() => setCopiedIndex(null), 2000)
  }

  function handleFileUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    send(`Summarize the document: ${file.name}`)
  }

  const activeConv = conversations.find((c) => c.id === conversationId)

  return (
    <div className="flex flex-col min-h-[calc(100vh-4rem)]">
      {/* Top Page Header */}
      <div className="bg-white border-b border-slate-200 px-6 sm:px-8 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">AI Assistant</h1>
            {activeConv && (
              <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200 truncate max-w-xs">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-600 shrink-0" />
                <span className="truncate">{activeConv.title || 'Active Conversation'}</span>
              </span>
            )}
          </div>
          <p className="text-sm text-slate-500 mt-0.5">
            Ask questions about your company documents. Get accurate, grounded answers with citations.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {isSignedIn && (
            <Button
              variant="secondary"
              size="sm"
              icon={historyOpen ? ChevronDownIcon : AssistantIcon}
              onClick={() => setHistoryOpen(!historyOpen)}
              className="relative"
              title={historyOpen ? 'Hide conversation history' : 'Show conversation history'}
            >
              <span>History</span>
              {conversations.length > 0 && (
                <span className="ml-1 px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded-full text-[10px] font-semibold">
                  {conversations.length}
                </span>
              )}
            </Button>
          )}
          <Button variant="secondary" size="sm" icon={PlusIcon} onClick={startNewConversation}>
            New Chat
          </Button>
          <Button
            variant="secondary"
            size="sm"
            icon={TrashIcon}
            onClick={startNewConversation}
            disabled={messages.length === 0}
          >
            Clear
          </Button>
        </div>
      </div>

      {/* Main Workspace: Flex container containing History Sidebar (when signed in) + Chat Grid */}
      <div className="flex-1 px-4 sm:px-8 py-6">
        <div className={`w-full ${isSignedIn && historyOpen ? 'max-w-[1600px]' : 'max-w-7xl'} mx-auto flex flex-col xl:flex-row gap-6 items-start transition-all duration-200`}>
          {/* ====================================================
              LEFT COLUMN: CONVERSATION HISTORY PANEL (AUTH ONLY)
              ==================================================== */}
          {isSignedIn && historyOpen && (
            <aside className="w-full xl:w-72 shrink-0 bg-white border border-slate-200 rounded-2xl p-4 shadow-xs flex flex-col max-h-[380px] xl:max-h-[820px] overflow-hidden min-w-0">
              {/* History Header */}
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
                <div className="flex items-center gap-2">
                  <AssistantIcon className="w-4 h-4 text-blue-600" />
                  <span className="font-bold text-xs text-slate-900">Chat History</span>
                  {conversations.length > 0 && (
                    <span className="px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-600">
                      {conversations.length}
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={startNewConversation}
                    className="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors cursor-pointer"
                    title="New Chat"
                  >
                    <PlusIcon className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => setHistoryOpen(false)}
                    className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                    title="Collapse History"
                  >
                    <XIcon className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Conversations List / Loading / Empty State */}
              <div className="flex-1 overflow-y-auto space-y-1.5 pr-1 -mr-1 min-h-[140px]">
                {historyLoading && conversations.length === 0 && (
                  <div className="flex flex-col items-center justify-center py-12 text-slate-400 text-xs">
                    <Spinner className="w-5 h-5 border-blue-600 mb-2" />
                    <span>Loading conversations...</span>
                  </div>
                )}

                {!historyLoading && conversations.length === 0 && (
                  <div className="text-center py-12 px-3">
                    <div className="w-10 h-10 rounded-xl bg-slate-50 border border-slate-200 flex items-center justify-center mx-auto mb-2 text-slate-400">
                      <AssistantIcon className="w-5 h-5" />
                    </div>
                    <div className="text-xs font-semibold text-slate-800">No conversations yet</div>
                    <div className="text-[11px] text-slate-400 mt-1 leading-relaxed">
                      Start a new conversation to see it here.
                    </div>
                  </div>
                )}

                {conversations.map((conv) => {
                  const isActive = conv.id === conversationId
                  const isLoadingThis = selectedLoadingId === conv.id
                  const isDeletingThis = deletingId === conv.id
                  const isEditingThis = editingId === conv.id
                  const isRenamingThis = renamingId === conv.id

                  return (
                    <div
                      key={conv.id}
                      onClick={() => !isEditingThis && handleSelectConversation(conv.id)}
                      className={`group relative p-2.5 rounded-xl border transition-all cursor-pointer flex flex-col justify-between gap-1.5 min-w-0 ${
                        isActive
                          ? 'bg-blue-50/80 border-blue-200 text-blue-900 shadow-2xs'
                          : 'bg-white hover:bg-slate-50 border-slate-200/80 text-slate-700 hover:border-slate-300'
                      } ${isLoadingThis || isDeletingThis ? 'opacity-70 pointer-events-none' : ''}`}
                    >
                      {isEditingThis ? (
                        <form
                          onSubmit={(e) => handleSaveRename(conv.id, e)}
                          onClick={(e) => e.stopPropagation()}
                          className="flex items-center gap-1.5 w-full py-0.5 min-w-0"
                        >
                          <input
                            ref={renameInputRef}
                            type="text"
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Escape') {
                                e.stopPropagation()
                                handleCancelRename(e)
                              }
                            }}
                            maxLength={100}
                            className="flex-1 min-w-0 text-xs border border-blue-400 rounded-lg px-2 py-1 text-slate-900 bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 shadow-2xs font-sans"
                            autoFocus
                          />
                          <button
                            type="submit"
                            disabled={!editTitle.trim() || isRenamingThis}
                            className="p-1 text-blue-600 hover:text-blue-800 hover:bg-blue-100/60 rounded transition-colors cursor-pointer shrink-0 disabled:opacity-40"
                            title="Save (Enter)"
                          >
                            {isRenamingThis ? (
                              <Spinner className="w-3.5 h-3.5 border-blue-600" />
                            ) : (
                              <CheckIcon className="w-3.5 h-3.5" />
                            )}
                          </button>
                          <button
                            type="button"
                            onClick={handleCancelRename}
                            className="p-1 text-slate-400 hover:text-slate-600 hover:bg-slate-200/60 rounded transition-colors cursor-pointer shrink-0"
                            title="Cancel (Esc)"
                          >
                            <XIcon className="w-3.5 h-3.5" />
                          </button>
                        </form>
                      ) : (
                        <div className="flex items-start justify-between gap-1.5 min-w-0">
                          <div className="flex items-center gap-2 min-w-0 flex-1">
                            <span
                              className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                                isActive ? 'bg-blue-600' : 'bg-slate-300 group-hover:bg-slate-400'
                              }`}
                            />
                            <span
                              className="text-xs font-medium truncate leading-tight text-slate-800"
                              title={conv.title || 'Untitled Conversation'}
                            >
                              {conv.title || 'Untitled Conversation'}
                            </span>
                          </div>

                          {/* Compact Action area (Rename + Delete) */}
                          <div className="flex items-center gap-0.5 shrink-0 opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100 transition-opacity">
                            <button
                              type="button"
                              onClick={(e) => handleStartRename(conv, e)}
                              className="p-1 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors cursor-pointer shrink-0"
                              title="Rename conversation"
                            >
                              <EditIcon className="w-3.5 h-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={(e) => handleDeleteConversation(conv.id, e)}
                              disabled={isDeletingThis}
                              className="p-1 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors cursor-pointer shrink-0"
                              title="Delete conversation"
                            >
                              {isDeletingThis ? (
                                <Spinner className="w-3.5 h-3.5 border-red-500" />
                              ) : (
                                <TrashIcon className="w-3.5 h-3.5" />
                              )}
                            </button>
                          </div>
                        </div>
                      )}

                      <div className="flex items-center justify-between text-[10px] text-slate-400 pl-3.5">
                        <span className="truncate">{formatCompactDate(conv.created_at)}</span>
                        {isLoadingThis && (
                          <span className="flex items-center gap-1 text-blue-600 font-medium shrink-0 ml-2">
                            <Spinner className="w-2.5 h-2.5 border-blue-600" />
                            <span>Loading...</span>
                          </span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </aside>
          )}

          {/* ====================================================
              MAIN WORKSPACE: CHAT & RIGHT EXECUTION PANEL
              ==================================================== */}
          <div className="flex-1 min-w-0 w-full grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* ====================================================
              LEFT/CENTER COLUMN: CHAT, COMPOSER, STATS
              ==================================================== */}
          <div className="lg:col-span-8 flex flex-col space-y-6">
            {/* Suggestion Cards Row (4 cards) */}
            <div className={`grid grid-cols-1 sm:grid-cols-2 ${isSignedIn && historyOpen ? '2xl:grid-cols-4' : 'xl:grid-cols-4'} gap-3.5`}>
              {SUGGESTIONS.map((item, idx) => {
                const Icon = item.icon
                const colorStyles = {
                  blue: 'bg-blue-50 text-blue-600 border-blue-100',
                  orange: 'bg-orange-50 text-orange-600 border-orange-100',
                  purple: 'bg-purple-50 text-purple-600 border-purple-100',
                }

                return (
                  <Card
                    key={idx}
                    onClick={() => send(item.question)}
                    className="p-3.5 hover:border-blue-300 hover:shadow-sm transition-all cursor-pointer group flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <div
                          className={`w-7 h-7 rounded-lg flex items-center justify-center border ${
                            colorStyles[item.color] || colorStyles.blue
                          }`}
                        >
                          <Icon className="w-4 h-4" />
                        </div>
                        <span className="font-semibold text-xs text-slate-900 group-hover:text-blue-600 transition-colors">
                          {item.category}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">
                        "{item.question}"
                      </p>
                    </div>
                  </Card>
                )
              })}
            </div>

            {/* Conversation Messages Container */}
            <div className="bg-white border border-slate-200 rounded-2xl p-4 sm:p-6 shadow-xs min-h-[420px] flex flex-col justify-between">
              <div className="space-y-6 flex-1">
                {selectedLoadingId ? (
                  <div className="h-full flex flex-col items-center justify-center text-center py-20 px-4">
                    <Spinner className="w-8 h-8 border-blue-600 mb-3" />
                    <div className="text-sm font-medium text-slate-700">Loading conversation messages...</div>
                  </div>
                ) : messages.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center py-16 px-4">
                    <div className="w-14 h-14 rounded-2xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600 mb-4 shadow-xs">
                      <NexaLogo className="w-8 h-8" />
                    </div>
                    <h2 className="text-base font-bold text-slate-900">
                      Welcome to Nexa AI Enterprise
                    </h2>
                    <p className="text-xs text-slate-500 max-w-md mt-1 leading-relaxed">
                      Select a topic above or ask any question about indexed enterprise policies. All
                      answers are verified through NeMo Guardrails and LangGraph reasoning.
                    </p>
                  </div>
                ) : null}

                {messages.map((msg, idx) => {
                  if (msg.role === 'user') {
                    return (
                      <div key={idx} className="flex items-start gap-3 justify-start max-w-2xl">
                        <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 font-semibold text-xs flex items-center justify-center shrink-0 shadow-2xs">
                          P
                        </div>
                        <div className="flex-1">
                          <div className="bg-slate-50 border border-slate-200 text-slate-900 rounded-2xl rounded-tl-sm px-4 py-3 text-sm shadow-2xs leading-relaxed font-normal">
                            {msg.content}
                          </div>
                          {msg.timestamp && (
                            <div className="text-[10px] text-slate-400 mt-1 pl-1 font-mono">
                              {msg.timestamp}
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  }

                  // Assistant Response Card
                  return (
                    <div key={idx} className="flex items-start gap-3 justify-start w-full">
                      <div className="w-8 h-8 rounded-full bg-slate-900 text-white flex items-center justify-center shrink-0 shadow-2xs p-1">
                        <NexaLogo className="w-6 h-6" />
                      </div>
                      <div className="flex-1 max-w-full">
                        <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-sm p-5 shadow-xs">
                          {/* Top Status Badge */}
                          <div className="flex items-center justify-between gap-2 mb-3 pb-3 border-b border-slate-100">
                            <div className="flex items-center gap-1.5">
                              <span className="text-xs font-bold text-slate-900">Nexa AI</span>
                              <span className="text-[10px] text-slate-400 font-mono">Enterprise V2</span>
                            </div>

                            {msg.grounded ? (
                              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                                <CheckCircleFilled className="w-3.5 h-3.5 text-blue-600" />
                                <span>Grounded in company documents</span>
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
                                <span>Evidence bounded / Refusal</span>
                              </span>
                            )}
                          </div>

                          {/* Formatted Answer Body */}
                          <FormattedAnswer text={msg.content} />

                          {/* Footer Actions & Metadata */}
                          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
                            <div className="flex items-center gap-3">
                              {msg.timestamp && <span className="font-mono">{msg.timestamp}</span>}
                              {msg.latency != null && (
                                <span className="font-mono text-slate-500">
                                  {(Number(msg.latency) / 1000).toFixed(2)}s
                                </span>
                              )}
                              {msg.status && (
                                <span className="text-[11px] text-slate-500 capitalize">
                                  {msg.status}
                                </span>
                              )}
                            </div>

                            <button
                              onClick={() => handleCopy(msg.content, idx)}
                              className="text-slate-400 hover:text-slate-700 flex items-center gap-1 text-xs py-1 px-2 rounded hover:bg-slate-100 transition-colors"
                              title="Copy response"
                            >
                              {copiedIndex === idx ? (
                                <>
                                  <CheckIcon className="w-3.5 h-3.5 text-blue-600" />
                                  <span className="text-blue-600 font-medium">Copied</span>
                                </>
                              ) : (
                                <>
                                  <CopyIcon className="w-3.5 h-3.5" />
                                  <span>Copy</span>
                                </>
                              )}
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  )
                })}

                {/* Loading State */}
                {loading && (
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-slate-900 text-white flex items-center justify-center shrink-0 p-1">
                      <NexaLogo className="w-6 h-6" />
                    </div>
                    <div className="bg-slate-50 border border-slate-200 rounded-2xl rounded-tl-sm p-4 shadow-2xs">
                      <div className="flex items-center gap-2.5 text-xs font-medium text-slate-600">
                        <Spinner className="w-4 h-4 border-blue-600" />
                        <span>Generating grounded answer via LangGraph pipeline...</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Error Banner */}
                {error && (
                  <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center gap-2">
                    <span>⚠ {error}</span>
                  </div>
                )}

                {/* History Error Banner */}
                {historyError && (
                  <div className="p-3 bg-amber-50 border border-amber-200 text-amber-700 text-xs rounded-xl flex items-center justify-between gap-2">
                    <span>⚠ {historyError}</span>
                    <button
                      type="button"
                      onClick={() => setHistoryError(null)}
                      className="text-amber-700 hover:text-amber-900 font-bold px-1 cursor-pointer"
                      title="Dismiss"
                    >
                      ×
                    </button>
                  </div>
                )}

                <div ref={bottomRef} />
              </div>
            </div>

            {/* Question Composer */}
            <Card className="p-4 bg-white border border-slate-200 shadow-xs">
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  send()
                }}
                className="space-y-3"
              >
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      send()
                    }
                  }}
                  rows={2}
                  disabled={loading}
                  placeholder="Ask your question about your knowledge base..."
                  className="w-full resize-none border-none p-1 text-sm text-slate-900 placeholder:text-slate-400 focus:ring-0 outline-none leading-relaxed"
                />

                <div className="pt-2 border-t border-slate-100 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={handleFileUpload}
                      className="hidden"
                      accept=".pdf,.txt,.docx"
                    />
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600 hover:text-slate-900 py-1.5 px-2.5 rounded-lg hover:bg-slate-100 transition-colors"
                    >
                      <PaperclipIcon className="w-3.5 h-3.5 text-slate-400" />
                      <span>Attach Document</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => setAdvancedMode(!advancedMode)}
                      className={`inline-flex items-center gap-1.5 text-xs font-medium py-1.5 px-2.5 rounded-lg transition-colors ${
                        advancedMode
                          ? 'bg-blue-50 text-blue-600 font-semibold'
                          : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                      }`}
                    >
                      <SlidersIcon className="w-3.5 h-3.5 text-slate-400" />
                      <span>Advanced Mode</span>
                    </button>
                  </div>

                  <Button
                    type="submit"
                    size="md"
                    variant="primary"
                    icon={SendIcon}
                    disabled={loading || !input.trim()}
                    className="shadow-xs"
                  >
                    Send
                  </Button>
                </div>
              </form>
            </Card>

            {/* Bottom 4 Metric Cards Row */}
            <div className={`grid grid-cols-1 sm:grid-cols-2 ${isSignedIn && historyOpen ? '2xl:grid-cols-4' : 'xl:grid-cols-4'} gap-4 pt-1 min-w-0`}>
              <MetricCard
                icon={FileTextIcon}
                iconColor="blue"
                label="Documents"
                value={docCount !== null ? String(docCount) : '—'}
                subtitle={docCount !== null && docCount > 0 ? "Indexed in vector DB" : "No documents indexed"}
              />
              <MetricCard
                icon={AssistantIcon}
                iconColor="blue"
                label="Total Queries"
                value={totalQueries > 0 ? String(totalQueries) : '0'}
                subtitle={totalQueries > 0 ? "Active session queries" : "Awaiting queries"}
              />
              <MetricCard
                icon={BoltIcon}
                iconColor="orange"
                label="Avg. Latency"
                value={avgLatency}
                subtitle={avgLatency !== '—' ? "Session average" : "Awaiting query"}
              />
              <MetricCard
                icon={DatabaseIcon}
                iconColor="purple"
                label="Cache Hit Rate"
                value={cacheHitRate}
                subtitle={cacheHitRate !== '—' ? "Dual-layer cache hits" : "In-memory cache ready"}
              />
            </div>
          </div>

          {/* ====================================================
              RIGHT COLUMN: AGENT EXECUTION & SOURCES
              ==================================================== */}
          <div className="lg:col-span-4 space-y-5">
            {/* Agent Execution Card */}
            <AgentExecutionPanel
              latencyMs={latestLatency}
              thoughtProcess={latestThoughtProcess}
              sourcesCount={latestSources.length}
              grounded={latestGrounded}
              query={latestQuery}
            />

            {/* Sources Evidence Card */}
            <SourceReceipt sources={latestSources} grounded={latestGrounded} />
          </div>
        </div>
      </div>
    </div>
  </div>
  )
}

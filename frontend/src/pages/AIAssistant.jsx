import React from 'react'
import { useRef, useState, useEffect } from 'react'
import PageHeader from '../components/PageHeader.jsx'
import { Card, Spinner } from '../components/ui.jsx'
import SourceReceipt from '../components/SourceReceipt.jsx'
import { api } from '../api/client.js'

const SUGGESTIONS = [
  'How often are employees paid?',
  'How long can the direct deposit process take?',
  'What is the normal workweek for employees?',
  'How long is the unpaid lunch period during a normal workday?',
]

export default function AIAssistant() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [conversationId, setConversationId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: 'smooth',
    })
  }, [messages, loading])

  async function send(question) {
    const q = (question ?? input).trim()

    if (!q || loading) return

    setInput('')
    setError(null)

    setMessages((messages) => [
      ...messages,
      {
        role: 'user',
        content: q,
      },
    ])

    setLoading(true)

    try {
      const response = await api.chat(
        q,
        conversationId,
      )

      setConversationId(
        response.conversation_id || null,
      )

      setMessages((messages) => [
        ...messages,
        {
          role: 'assistant',
          content: response.answer,
          sources: response.sources || [],
          grounded: response.grounded,
          latency: response.latency_ms,
        },
      ])
    } catch (error) {
      setError(error.message)

      setMessages((messages) => [
        ...messages,
        {
          role: 'assistant',
          content:
            'I was unable to process your question. Please try again.',
          sources: [],
          grounded: false,
        },
      ])
    } finally {
      setLoading(false)
    }
  }

  function startNewConversation() {
    setMessages([])
    setConversationId(null)
    setInput('')
    setError(null)
  }

  return (
    <div className="flex flex-col h-screen">
      <PageHeader
        eyebrow="Ask NexaAI"
        title="AI Assistant"
        description="Ask questions about your indexed documents. Answers are grounded in retrieved knowledge-base content."
        action={
          messages.length > 0 ? (
            <button
              onClick={startNewConversation}
              className="px-4 py-2 rounded-md text-sm bg-transparent text-mist-200 border border-ink-600 hover:bg-ink-700"
            >
              New conversation
            </button>
          ) : null
        }
      />

      <div className="flex-1 overflow-y-auto px-8 py-6">
        {messages.length === 0 && (
          <div className="max-w-3xl mb-8">
            <div className="mb-5">
              <p className="text-sm text-mist-200 font-medium">
                Ask about your knowledge base
              </p>

              <p className="text-xs text-mist-400 mt-1">
                NexaAI retrieves relevant document chunks before generating an answer.
              </p>
            </div>

            <p className="text-xs text-mist-400 mb-3">
              Try asking:
            </p>

            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => send(suggestion)}
                  disabled={loading}
                  className="text-xs font-mono px-3 py-2 rounded-md border border-ink-600 text-mist-300 hover:border-signal-teal/40 hover:text-signal-teal disabled:opacity-40 transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="space-y-5 max-w-3xl">
          {messages.map((message, index) =>
            message.role === 'user' ? (
              <div
                key={index}
                className="flex justify-end"
              >
                <div className="bg-signal-indigo/15 border border-signal-indigo/30 text-mist-50 rounded-lg px-4 py-3 max-w-lg text-sm">
                  {message.content}
                </div>
              </div>
            ) : (
              <div
                key={index}
                className="flex justify-start"
              >
                <Card className="px-4 py-4 max-w-xl w-full">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-6 h-6 rounded-md bg-signal-teal/10 border border-signal-teal/30 flex items-center justify-center text-signal-teal text-xs font-semibold">
                      N
                    </div>

                    <span className="text-xs font-mono text-mist-400">
                      NexaAI
                    </span>
                  </div>

                  <p className="text-sm text-mist-100 whitespace-pre-wrap leading-relaxed">
                    {message.content}
                  </p>

                  <SourceReceipt
                    sources={message.sources}
                    grounded={message.grounded}
                  />

                  {message.latency != null && (
                    <div className="text-[10px] font-mono text-mist-400 mt-2">
                      {message.latency.toFixed(0)}ms
                    </div>
                  )}
                </Card>
              </div>
            ),
          )}

          {loading && (
            <div className="flex items-center gap-2 text-mist-400 text-sm">
              <Spinner />
              retrieving context & generating...
            </div>
          )}

          {error && (
            <div className="text-sm text-signal-coral">
              {error}
            </div>
          )}
        </div>

        <div ref={bottomRef} />
      </div>

      <div className="border-t border-ink-700 px-8 py-4">
        <form
          onSubmit={(event) => {
            event.preventDefault()
            send()
          }}
          className="flex gap-3 max-w-3xl"
        >
          <input
            value={input}
            onChange={(event) =>
              setInput(event.target.value)
            }
            placeholder="Ask a question about your documents..."
            disabled={loading}
            className="flex-1 bg-ink-800 border border-ink-600 rounded-md px-4 py-2.5 text-sm text-mist-50 placeholder:text-mist-400 focus:border-signal-teal/50 outline-none disabled:opacity-50"
          />

          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="px-5 py-2.5 rounded-md bg-signal-teal text-ink-950 text-sm font-medium hover:bg-signal-teal/90 disabled:opacity-40"
          >
            Ask
          </button>
        </form>
      </div>
    </div>
  )
}
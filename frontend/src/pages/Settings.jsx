import React from 'react'
import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader.jsx'
import { Card, Badge } from '../components/ui.jsx'
import { api } from '../api/client.js'

export default function Settings() {
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.health().then(setHealth).catch((e) => setError(e.message))
  }, [])

  return (
    <div>
      <PageHeader
        eyebrow="Configuration"
        title="Settings"
        description="NexaAI is configured via backend/.env — this page reflects the running configuration read-only."
      />

      <div className="px-8 py-6 max-w-2xl space-y-4">
        {error && <p className="text-sm text-signal-coral">{error}</p>}

        <Card className="p-5">
          <h2 className="font-display text-sm font-semibold text-mist-50 mb-4">LLM Provider</h2>
          <Row label="Provider" value="Gemini" />
          <Row label="Model" value={health?.gemini_model ?? '—'} mono />
          <Row
            label="API key"
            value={
              <Badge tone={health?.gemini_configured ? 'good' : 'warn'}>
                {health?.gemini_configured ? 'configured' : 'not set — set GEMINI_API_KEY in backend/.env'}
              </Badge>
            }
          />
        </Card>

        <Card className="p-5">
          <h2 className="font-display text-sm font-semibold text-mist-50 mb-4">Retrieval</h2>
          <Row label="Embedding model" value={health?.embedding_model ?? '—'} mono />
          <Row label="Vector index" value="FAISS (local, cosine similarity)" mono />
          <Row label="Chunking" value="~700 tokens, overlap, page-aware" mono />
        </Card>

        <Card className="p-5">
          <h2 className="font-display text-sm font-semibold text-mist-50 mb-4">Storage</h2>
          <Row label="Structured data" value="SQLite (backend/data/nexaai.db)" mono />
          <Row label="Documents" value="Local disk (backend/data/uploads)" mono />
          <p className="text-xs text-mist-400 mt-3">
            Future production deployments can swap these for PostgreSQL + Qdrant + object storage without changing
            the API surface — see Section 20/21 of the project spec.
          </p>
        </Card>
      </div>
    </div>
  )
}

function Row({ label, value, mono }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-ink-700/60 last:border-0 text-sm">
      <span className="text-mist-400">{label}</span>
      <span className={mono ? 'font-mono text-mist-200 text-xs' : 'text-mist-200'}>{value}</span>
    </div>
  )
}

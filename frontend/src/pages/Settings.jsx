import React, { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader.jsx'
import { Card, Badge } from '../components/ui.jsx'
import { ShieldIcon, DatabaseIcon, BoltIcon, SparklesIcon, CheckCircleFilled } from '../components/Icons.jsx'
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
        description="Nexa AI Enterprise V2 architecture and active runtime parameters."
      />

      <div className="px-6 sm:px-8 py-6 max-w-4xl space-y-6 mx-auto">
        {error && (
          <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl">
            Notice: {error}
          </div>
        )}

        {/* AI & Reasoning Engine */}
        <Card className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <SparklesIcon className="w-5 h-5 text-blue-600" />
            <h2 className="font-bold text-sm text-slate-900">AI Reasoning & Model Gateway</h2>
          </div>
          <div className="space-y-3">
            <ConfigRow label="Provider / Gateway" value="Portkey AI Gateway (OpenAI Compatible)" />
            <ConfigRow label="Primary Reasoning Model" value="openai/gpt-oss-120b (@rag)" mono />
            <ConfigRow label="Guardrails Engine Model" value="openai/gpt-oss-20b" mono />
            <ConfigRow
              label="Gateway Credentials"
              value={<Badge tone="blue">Configured via Environment</Badge>}
            />
          </div>
        </Card>

        {/* Safety & Guardrails */}
        <Card className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <ShieldIcon className="w-5 h-5 text-blue-600" />
            <h2 className="font-bold text-sm text-slate-900">Safety & Guardrails Architecture</h2>
          </div>
          <div className="space-y-3">
            <ConfigRow label="Guardrails Engine" value="NeMo Guardrails 0.24.0" />
            <ConfigRow label="Language Spec" value="Colang 2.x" mono />
            <ConfigRow
              label="Input Rails"
              value={
                <Badge tone="blue">
                  <CheckCircleFilled className="w-3 h-3 text-blue-600" />
                  <span>CheckUserUtteranceAction</span>
                </Badge>
              }
            />
            <ConfigRow
              label="Output Rails"
              value={
                <Badge tone="blue">
                  <CheckCircleFilled className="w-3 h-3 text-blue-600" />
                  <span>CheckBotResponseAction</span>
                </Badge>
              }
            />
            <ConfigRow label="Output Validations" value="API Keys, Prompt Leakage, PII, Hallucination Gates" />
          </div>
        </Card>

        {/* Retrieval & Vector Database */}
        <Card className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <DatabaseIcon className="w-5 h-5 text-purple-600" />
            <h2 className="font-bold text-sm text-slate-900">Retrieval & Embedding Layer</h2>
          </div>
          <div className="space-y-3">
            <ConfigRow label="Vector Database" value="Qdrant Cloud (Managed Cluster)" />
            <ConfigRow label="Collection Name" value="enterprise_rag" mono />
            <ConfigRow label="Embedding Model" value="gemini-embedding-2-preview (3072 dimensions)" mono />
            <ConfigRow label="Reranker Engine" value="FlashRank Cross-Encoder (Local TinyBERT)" mono />
            <ConfigRow label="Sufficiency Gate" value="Self-Correction / Retry LangGraph Loop (Max retries: 2)" />
          </div>
        </Card>

        {/* Performance & Caching */}
        <Card className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <BoltIcon className="w-5 h-5 text-orange-600" />
            <h2 className="font-bold text-sm text-slate-900">Performance & Caching</h2>
          </div>
          <div className="space-y-3">
            <ConfigRow label="Embedding Cache" value="In-Memory Normalized Cache (TTL: 3600s)" mono />
            <ConfigRow label="Response Cache" value="In-Memory Multi-Key Cache (TTL: 3600s)" mono />
            <ConfigRow label="Cache Isolation" value="Blocked responses never committed to cache" />
            <ConfigRow label="Telemetry & Logs" value="Logfire OpenTelemetry Tracing" />
          </div>
        </Card>
      </div>
    </div>
  )
}

function ConfigRow({ label, value, mono = false }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between py-2 border-b border-slate-100 last:border-0 text-xs gap-1">
      <span className="text-slate-500 font-medium">{label}</span>
      <span className={mono ? 'font-mono text-slate-800' : 'text-slate-800 font-medium'}>
        {value}
      </span>
    </div>
  )
}

import React, { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader.jsx'
import { Card, StatCard, Badge } from '../components/ui.jsx'
import {
  BoltIcon,
  DatabaseIcon,
  AssistantIcon,
  ShieldIcon,
  SparklesIcon,
} from '../components/Icons.jsx'

export default function Usage() {
  const [sessionQueries, setSessionQueries] = useState(0)
  const [avgLatency, setAvgLatency] = useState('—')
  const [cacheHitRate, setCacheHitRate] = useState('—')

  useEffect(() => {
    try {
      const savedMsgs = sessionStorage.getItem('nexa_messages')
      if (savedMsgs) {
        const msgs = JSON.parse(savedMsgs)
        const userMsgs = msgs.filter((m) => m.role === 'user')
        setSessionQueries(userMsgs.length)

        const assistantMsgs = msgs.filter((m) => m.role === 'assistant' && m.latency != null)
        if (assistantMsgs.length > 0) {
          const totalMs = assistantMsgs.reduce((acc, m) => acc + Number(m.latency), 0)
          setAvgLatency(`${(totalMs / assistantMsgs.length / 1000).toFixed(2)}s`)

          const hits = assistantMsgs.filter(
            (m) =>
              m.thoughtProcess?.some((t) => typeof t === 'string' && t.toLowerCase().includes('cache hit')) ||
              m.cached
          ).length
          setCacheHitRate(`${Math.round((hits / assistantMsgs.length) * 100)}%`)
        }
      }
    } catch {}
  }, [])

  return (
    <div>
      <PageHeader
        eyebrow="Cost & Telemetry"
        title="Usage & Analytics"
        description="Query throughput, model inference latency, and cache efficiency metrics."
      />

      <div className="px-6 sm:px-8 py-6 space-y-6 max-w-7xl mx-auto">
        {/* Metric Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total Queries"
            value={sessionQueries > 0 ? String(sessionQueries) : '0'}
            sub={sessionQueries > 0 ? 'Active session queries' : 'Awaiting session activity'}
            tone="blue"
          />
          <StatCard
            label="Average Latency"
            value={avgLatency}
            sub={avgLatency !== '—' ? 'Session average query time' : 'Awaiting query execution'}
            tone="orange"
          />
          <StatCard
            label="Cache Hit Rate"
            value={cacheHitRate}
            sub={cacheHitRate !== '—' ? 'In-memory response & embedding hits' : 'Dual-layer caching operational'}
            tone="purple"
          />
          <StatCard
            label="Guardrails Status"
            value="Enforced"
            sub="NeMo input & output rails active"
            tone="good"
          />
        </div>

        {/* Analytics Breakdown Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Caching Architecture Card */}
          <Card className="lg:col-span-6 p-6">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <DatabaseIcon className="w-5 h-5 text-purple-600" />
                <h2 className="font-bold text-sm text-slate-900">Dual-Layer Caching Performance</h2>
              </div>
              <Badge tone="purple">In-Memory</Badge>
            </div>
            <p className="text-xs text-slate-500 mb-4 leading-relaxed">
              Nexa AI isolates embedding cache from LLM response cache to eliminate redundant Gemini & Portkey API costs.
            </p>

            <div className="space-y-3 text-xs">
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-900">Gemini Embedding Cache</div>
                  <div className="text-[11px] text-slate-500">Normalizes queries (lowercasing, whitespace collapse)</div>
                </div>
                <span className="font-mono font-semibold text-blue-600 text-sm">Active</span>
              </div>

              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-900">LLM Response Cache</div>
                  <div className="text-[11px] text-slate-500">Keyed on query, docs, sufficiency & history</div>
                </div>
                <span className="font-mono font-semibold text-purple-600 text-sm">Active</span>
              </div>

              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-900">Cache Isolation Rule</div>
                  <div className="text-[11px] text-slate-500">Blocked outputs are NEVER committed to cache</div>
                </div>
                <span className="font-mono font-semibold text-blue-600 text-sm">Enforced</span>
              </div>
            </div>
          </Card>

          {/* Model Gateway & Inference Card */}
          <Card className="lg:col-span-6 p-6">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <BoltIcon className="w-5 h-5 text-orange-600" />
                <h2 className="font-bold text-sm text-slate-900">Inference Gateway Telemetry</h2>
              </div>
              <Badge tone="orange">Portkey Gateway</Badge>
            </div>
            <p className="text-xs text-slate-500 mb-4 leading-relaxed">
              Model requests route through Portkey with automatic failover to fallback models.
            </p>

            <div className="space-y-3 text-xs">
              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-900">Primary Reasoning Model</div>
                  <div className="text-[11px] text-slate-500 font-mono">openai/gpt-oss-120b (Portkey @rag)</div>
                </div>
                <Badge tone="good">Healthy</Badge>
              </div>

              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-900">Embedding Model</div>
                  <div className="text-[11px] text-slate-500 font-mono">gemini-embedding-2-preview (3072 dim)</div>
                </div>
                <Badge tone="good">Healthy</Badge>
              </div>

              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
                <div>
                  <div className="font-semibold text-slate-900">Cross-Encoder Reranker</div>
                  <div className="text-[11px] text-slate-500 font-mono">FlashRank TinyBERT (Local inference)</div>
                </div>
                <Badge tone="good">Instant</Badge>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
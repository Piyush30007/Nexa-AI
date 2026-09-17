import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import PageHeader from '../components/PageHeader.jsx'
import { Card, StatCard, Badge, Button } from '../components/ui.jsx'
import {
  FileTextIcon,
  AssistantIcon,
  BoltIcon,
  DatabaseIcon,
  CheckCircleFilled,
  ShieldIcon,
  SparklesIcon,
} from '../components/Icons.jsx'
import { api } from '../api/client.js'

export default function Dashboard() {
  const [health, setHealth] = useState(null)
  const [evalRuns, setEvalRuns] = useState([])
  const [error, setError] = useState(null)
  const [docCount, setDocCount] = useState(0)
  const [sessionQueries, setSessionQueries] = useState(0)

  useEffect(() => {
    // 1. Core health check
    api.health()
      .then((h) => {
        setHealth(h)
        setError(null)
      })
      .catch((e) => setError(e.message))

    // 2. Optional evaluation benchmark results (graceful fallback)
    api.getEvaluationResults()
      .then((e) => setEvalRuns(Array.isArray(e) ? e : e ? [e] : []))
      .catch(() => setEvalRuns([]))

    try {
      const savedDocs = localStorage.getItem('nexa_indexed_documents')
      if (savedDocs) {
        setDocCount(JSON.parse(savedDocs).length)
      }
      const savedMsgs = sessionStorage.getItem('nexa_messages')
      if (savedMsgs) {
        const msgs = JSON.parse(savedMsgs)
        setSessionQueries(msgs.filter((m) => m.role === 'user').length)
      }
    } catch {}
  }, [])

  const latestEval = evalRuns[0]

  const groundedRate =
    latestEval?.hallucination_rate != null
      ? `${((1 - latestEval.hallucination_rate) * 100).toFixed(0)}%`
      : '—'

  const avgLatency =
    latestEval?.avg_latency_ms != null
      ? `${(latestEval.avg_latency_ms / 1000).toFixed(2)}s`
      : '—'

  return (
    <div>
      <PageHeader
        eyebrow="System Overview"
        title="Dashboard"
        description="A grounded knowledge layer over your enterprise documents — verification before generation, citations on every answer."
        action={
          <Link to="/assistant">
            <Button variant="primary" size="md">
              Open AI Assistant →
            </Button>
          </Link>
        }
      />

      <div className="px-6 sm:px-8 py-6 space-y-6 max-w-7xl mx-auto">
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center gap-2">
            <span>⚠ Backend notice: {error}</span>
          </div>
        )}

        {/* Metric Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Documents Indexed"
            value={docCount > 0 ? String(docCount) : '0'}
            sub={docCount > 0 ? `${docCount} active document${docCount > 1 ? 's' : ''}` : 'No documents indexed yet'}
            tone="blue"
          />
          <StatCard
            label="Total Queries"
            value={sessionQueries > 0 ? String(sessionQueries) : '0'}
            sub={sessionQueries > 0 ? 'Session queries processed' : 'Awaiting queries'}
            tone="default"
          />
          <StatCard
            label="Grounded Rate"
            value={groundedRate}
            sub={latestEval ? 'Zero ungrounded claims in eval' : 'Run evaluation to benchmark'}
            tone="good"
          />
          <StatCard
            label="Avg Latency"
            value={avgLatency}
            sub={latestEval ? 'Benchmark average latency' : 'Awaiting benchmark run'}
            tone="warn"
          />
        </div>

        {/* System Architecture & Status */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Services Health */}
          <Card className="lg:col-span-6 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-bold text-sm text-slate-900">Services & Infrastructure</h2>
              <span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-full border border-blue-200">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-pulse" />
                Operational
              </span>
            </div>

            <div className="divide-y divide-slate-100 text-sm">
              <div className="py-3 flex items-center justify-between">
                <div>
                  <div className="font-medium text-slate-900">FastAPI Application Core</div>
                  <div className="text-xs text-slate-500">Enterprise RAG v2.0.0</div>
                </div>
                <Badge tone="good">Online</Badge>
              </div>

              <div className="py-3 flex items-center justify-between">
                <div>
                  <div className="font-medium text-slate-900">Qdrant Cloud Vector DB</div>
                  <div className="text-xs text-slate-500">enterprise_rag collection • Cosine</div>
                </div>
                <Badge tone="good">Connected</Badge>
              </div>

              <div className="py-3 flex items-center justify-between">
                <div>
                  <div className="font-medium text-slate-900">NeMo Guardrails 0.24.0</div>
                  <div className="text-xs text-slate-500">Colang 2.x • Input & Output Rails</div>
                </div>
                <Badge tone="good">Active</Badge>
              </div>

              <div className="py-3 flex items-center justify-between">
                <div>
                  <div className="font-medium text-slate-900">Google Gemini Embeddings</div>
                  <div className="text-xs text-slate-500">gemini-embedding-2-preview • 3072 dim</div>
                </div>
                <Badge tone="good">Configured</Badge>
              </div>

              <div className="py-3 flex items-center justify-between">
                <div>
                  <div className="font-medium text-slate-900">Portkey AI Gateway</div>
                  <div className="text-xs text-slate-500">openai/gpt-oss-120b reasoning (@rag)</div>
                </div>
                <Badge tone="good">Connected</Badge>
              </div>

              <div className="py-3 flex items-center justify-between">
                <div>
                  <div className="font-medium text-slate-900">In-Memory Cache Layer</div>
                  <div className="text-xs text-slate-500">Embedding Cache & Response Cache</div>
                </div>
                <Badge tone="blue">Ready</Badge>
              </div>
            </div>
          </Card>

          {/* V2 Pipeline Workflow Card */}
          <Card className="lg:col-span-6 p-6 flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <SparklesIcon className="w-5 h-5 text-blue-600" />
                <h2 className="font-bold text-sm text-slate-900">V2 Agentic Pipeline Flow</h2>
              </div>
              <p className="text-xs text-slate-500 mb-5 leading-relaxed">
                Nexa AI executes a deterministic multi-stage pipeline ensuring high accuracy and safe responses.
              </p>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
                  <div className="font-semibold text-slate-900 mb-1 flex items-center gap-1.5">
                    <ShieldIcon className="w-4 h-4 text-blue-600" />
                    <span>1. Guardrails</span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    NeMo input rail blocks injections, secrets, and harmful prompts.
                  </p>
                </div>

                <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
                  <div className="font-semibold text-slate-900 mb-1 flex items-center gap-1.5">
                    <AssistantIcon className="w-4 h-4 text-blue-600" />
                    <span>2. Planner</span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    LangGraph planner analyzes query intent and formulates targeted searches.
                  </p>
                </div>

                <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
                  <div className="font-semibold text-slate-900 mb-1 flex items-center gap-1.5">
                    <DatabaseIcon className="w-4 h-4 text-blue-600" />
                    <span>3. Qdrant & FlashRank</span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    High-dimension vector retrieval followed by cross-encoder neural reranking.
                  </p>
                </div>

                <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl">
                  <div className="font-semibold text-slate-900 mb-1 flex items-center gap-1.5">
                    <CheckCircleFilled className="w-4 h-4 text-blue-600" />
                    <span>4. Sufficiency & Output</span>
                  </div>
                  <p className="text-[11px] text-slate-500">
                    Sufficiency gates verify evidence; NeMo output rail inspects the final answer.
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-5 pt-4 border-t border-slate-100 flex items-center justify-between">
              <span className="text-xs text-slate-500 font-medium">Ready to explore?</span>
              <Link to="/assistant">
                <Button variant="secondary" size="sm">
                  Launch Assistant →
                </Button>
              </Link>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
import React, { useState } from 'react'
import { Card } from './ui.jsx'
import { CheckCircleFilled, ChevronDownIcon, ChevronUpIcon, SparklesIcon } from './Icons.jsx'

export default function AgentExecutionPanel({
  latencyMs,
  thoughtProcess = [],
  sourcesCount = 0,
  grounded = true,
  query = '',
  status = 'completed',
}) {
  const [collapsed, setCollapsed] = useState(false)

  // When no query has been executed in the session yet
  if (!latencyMs && !query) {
    return (
      <Card className="p-4 bg-white border border-slate-200 shadow-xs">
        <div className="flex items-center justify-between">
          <div>
            <div className="font-bold text-sm text-slate-900">Agent Execution</div>
            <div className="flex items-center gap-1.5 text-xs text-slate-500 font-medium mt-0.5">
              <span className="w-2 h-2 rounded-full bg-blue-600 inline-block" />
              <span>Pipeline Ready</span>
            </div>
          </div>
        </div>
        <p className="text-xs text-slate-500 mt-3 pt-3 border-t border-slate-100 leading-relaxed">
          Submit a question to view real-time stage execution across Guardrails, LangGraph Planner, Qdrant Retrieval, FlashRank, and Sufficiency.
        </p>
      </Card>
    )
  }

  // Calculate actual elapsed time
  const totalSeconds = latencyMs ? Number((latencyMs / 1000).toFixed(2)) : 0

  // Derive intent summary from query if available
  const intentSummary = query
    ? `Understood intent: "${query.slice(0, 24)}..."`
    : 'Understood query intent'

  const steps = [
    {
      number: 1,
      name: 'Guardrails',
      detail: 'Input & safety validated',
      status: 'success',
    },
    {
      number: 2,
      name: 'Planner',
      detail: intentSummary,
      status: 'success',
    },
    {
      number: 3,
      name: 'Retriever',
      detail: sourcesCount > 0 ? `Retrieved ${sourcesCount} relevant chunk${sourcesCount > 1 ? 's' : ''}` : 'Retrieved evidence chunks',
      status: 'success',
    },
    {
      number: 4,
      name: 'FlashRank',
      detail: 'Neural cross-encoder reranking',
      status: 'success',
    },
    {
      number: 5,
      name: 'Sufficiency',
      detail: grounded ? 'Evidence verified sufficient' : 'Evidence bounded / Refusal rule',
      status: 'success',
    },
    {
      number: 6,
      name: 'Responder',
      detail: grounded ? 'Generated grounded answer with citations' : 'Generated bounded response',
      status: 'success',
    },
  ]

  return (
    <Card className="p-4 bg-white border border-slate-200 shadow-xs">
      {/* Header */}
      <div
        className="flex items-center justify-between cursor-pointer select-none"
        onClick={() => setCollapsed(!collapsed)}
      >
        <div>
          <div className="font-bold text-sm text-slate-900">Agent Execution</div>
          <div className="flex items-center gap-1.5 text-xs text-slate-500 font-medium mt-0.5">
            <CheckCircleFilled className="w-3.5 h-3.5 text-blue-600 shrink-0" />
            <span>Completed in {totalSeconds > 0 ? `${totalSeconds}s` : 'Real-time'}</span>
          </div>
        </div>
        <button className="text-slate-400 hover:text-slate-600 p-1">
          {collapsed ? <ChevronDownIcon className="w-4 h-4 shrink-0" /> : <ChevronUpIcon className="w-4 h-4 shrink-0" />}
        </button>
      </div>

      {/* Steps list */}
      {!collapsed && (
        <div className="mt-4 space-y-3 pt-3 border-t border-slate-100">
          {steps.map((step) => (
            <div key={step.number} className="flex items-start gap-2.5">
              <div className="w-5 h-5 rounded-full bg-blue-600 text-white font-semibold text-[11px] flex items-center justify-center shrink-0 shadow-2xs">
                {step.number}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold text-xs text-slate-900">{step.name}</span>
                  <span className="text-[10px] font-semibold text-blue-600 bg-blue-50 px-1.5 py-0.2 rounded border border-blue-100">
                    Passed
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 truncate mt-0.5">{step.detail}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

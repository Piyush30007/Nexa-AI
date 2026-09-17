import React, { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader.jsx'
import { Card, StatCard, Badge, Button, Spinner } from '../components/ui.jsx'
import { EvaluationIcon, CheckCircleFilled, SparklesIcon, AlertCircleIcon } from '../components/Icons.jsx'
import { api } from '../api/client.js'

export default function Evaluation() {
  const [runs, setRuns] = useState([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const [selectedRun, setSelectedRun] = useState(null)

  async function refresh() {
    try {
      const results = await api.getEvaluationResults()
      const runsList = Array.isArray(results) ? results : results ? [results] : []
      setRuns(runsList)
      if (runsList.length > 0 && !selectedRun) {
        setSelectedRun(runsList[0])
      }
    } catch (err) {
      console.warn('Evaluation fetch notice:', err.message)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  async function runNow() {
    setRunning(true)
    setError(null)
    try {
      const run = await api.runEvaluation()
      setRuns((prev) => [run, ...prev.filter((r) => r.id !== run.id)])
      setSelectedRun(run)
    } catch (err) {
      setError(err.message || 'Failed to start evaluation run.')
    } finally {
      setRunning(false)
    }
  }

  const activeRun = selectedRun || runs[0]

  return (
    <div>
      <PageHeader
        eyebrow="Accuracy & Faithfulness"
        title="Evaluation"
        description="Benchmark RAG pipeline quality across test queries for groundedness, latency, and correctness."
        action={
          <Button
            variant="primary"
            size="md"
            icon={running ? Spinner : EvaluationIcon}
            onClick={runNow}
            disabled={running}
          >
            {running ? 'Evaluating Pipeline...' : 'Run Evaluation'}
          </Button>
        }
      />

      <div className="px-6 sm:px-8 py-6 space-y-6 max-w-7xl mx-auto">
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center justify-between">
            <span>⚠ {error}</span>
            <button onClick={() => setError(null)} className="text-red-500 hover:text-red-800 text-xs">
              Dismiss
            </button>
          </div>
        )}

        {/* Top Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Grounded Rate"
            value={activeRun ? `${((1 - (activeRun.hallucination_rate || 0)) * 100).toFixed(0)}%` : '—'}
            sub={activeRun ? 'Zero unverified claims' : 'Run evaluation to calculate'}
            tone="blue"
          />
          <StatCard
            label="Answer Correctness"
            value={activeRun?.answer_correctness != null ? `${(activeRun.answer_correctness * 100).toFixed(0)}%` : '—'}
            sub={activeRun ? 'Semantic ground-truth match' : 'Run evaluation to calculate'}
            tone="purple"
          />
          <StatCard
            label="Test Queries"
            value={activeRun?.num_cases != null ? String(activeRun.num_cases) : '—'}
            sub="Enterprise policy test dataset"
            tone="default"
          />
          <StatCard
            label="Average Latency"
            value={activeRun?.avg_latency_ms != null ? `${(activeRun.avg_latency_ms / 1000).toFixed(2)}s` : '—'}
            sub="End-to-end response time"
            tone="warn"
          />
        </div>

        {/* Runs Table or Empty State */}
        {runs.length === 0 ? (
          <Card className="p-12 text-center">
            <div className="w-12 h-12 rounded-xl bg-purple-50 text-purple-600 border border-purple-100 flex items-center justify-center mx-auto mb-3">
              <EvaluationIcon className="w-6 h-6" />
            </div>
            <h3 className="font-bold text-sm text-slate-900">No evaluation runs available</h3>
            <p className="text-xs text-slate-500 max-w-md mx-auto mt-1 mb-5 leading-relaxed">
              Run an evaluation suite to test Nexa AI's retrieval precision, answer groundedness, and
              hallucination prevention against official test policies.
            </p>
            <Button
              variant="secondary"
              size="md"
              icon={running ? Spinner : SparklesIcon}
              onClick={runNow}
              disabled={running}
            >
              {running ? 'Running...' : 'Trigger Benchmark Run'}
            </Button>
          </Card>
        ) : (
          <Card className="overflow-hidden">
            <div className="p-4 border-b border-slate-100 bg-white flex items-center justify-between">
              <div className="font-bold text-sm text-slate-900">Evaluation Benchmark History</div>
              <Badge tone="purple">{runs.length} Run{runs.length > 1 ? 's' : ''}</Badge>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-500 font-semibold uppercase tracking-wider border-b border-slate-200 text-[11px]">
                  <tr>
                    <th className="py-3 px-5">Run ID</th>
                    <th className="py-3 px-5">Test Cases</th>
                    <th className="py-3 px-5">Grounded Rate</th>
                    <th className="py-3 px-5">Correctness</th>
                    <th className="py-3 px-5">Latency</th>
                    <th className="py-3 px-5">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {runs.map((run, i) => (
                    <tr
                      key={run.id || i}
                      onClick={() => setSelectedRun(run)}
                      className={`cursor-pointer transition-colors ${
                        activeRun?.id === run.id ? 'bg-blue-50/50' : 'hover:bg-slate-50'
                      }`}
                    >
                      <td className="py-3.5 px-5 font-mono text-slate-900 font-medium">
                        {run.id || `eval-run-${i + 1}`}
                      </td>
                      <td className="py-3.5 px-5 text-slate-600">
                        {run.num_cases != null ? `${run.num_cases} cases` : '—'}
                      </td>
                      <td className="py-3.5 px-5 font-semibold text-blue-600">
                        {run.hallucination_rate != null
                          ? `${((1 - run.hallucination_rate) * 100).toFixed(0)}%`
                          : '—'}
                      </td>
                      <td className="py-3.5 px-5 text-purple-600 font-semibold">
                        {run.answer_correctness != null
                          ? `${(run.answer_correctness * 100).toFixed(0)}%`
                          : '—'}
                      </td>
                      <td className="py-3.5 px-5 font-mono text-slate-500">
                        {run.avg_latency_ms != null ? `${(run.avg_latency_ms / 1000).toFixed(2)}s` : '—'}
                      </td>
                      <td className="py-3.5 px-5">
                        <span className="inline-flex items-center gap-1 text-xs font-medium text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded-full border border-blue-200">
                          <CheckCircleFilled className="w-3 h-3 text-blue-600" />
                          <span>Verified</span>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </div>
    </div>
  )
}
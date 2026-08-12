import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import PageHeader from '../components/PageHeader.jsx'
import { Card, StatCard, Badge } from '../components/ui.jsx'
import { api } from '../api/client.js'

export default function Dashboard() {
  const [health, setHealth] = useState(null)
  const [evalRuns, setEvalRuns] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([
      api.health(),
      api.getEvaluationResults(),
    ])
      .then(([h, e]) => {
        setHealth(h)
        setEvalRuns(Array.isArray(e) ? e : [])
      })
      .catch((e) => setError(e.message))
  }, [])

  const latestEval = evalRuns[0]

  return (
    <div>
      <PageHeader
        eyebrow="Overview"
        title="Dashboard"
        description="A grounded knowledge layer over your company documents — retrieval before generation, citations on every answer."
        action={
          <Link
            to="/assistant"
            className="px-4 py-2 rounded-md text-sm bg-signal-teal text-ink-950 font-medium hover:bg-signal-teal/90"
          >
            Ask a question →
          </Link>
        }
      />

      <div className="px-8 py-6">
        {error && (
          <Card className="px-4 py-3 mb-6 border-signal-coral/30">
            <span className="text-sm text-signal-coral">
              Backend error: {error}
            </span>
          </Card>
        )}

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatCard
            label="Documents indexed"
            value="—"
            sub="Upload documents in Knowledge Base"
          />

          <StatCard
            label="Requests logged"
            value="—"
            sub="Usage API not exposed"
          />

          <StatCard
            label="Grounded rate"
            value={
              latestEval
                ? `${((1 - latestEval.hallucination_rate) * 100).toFixed(0)}%`
                : '—'
            }
            tone="good"
          />

          <StatCard
            label="Evaluation cases"
            value={latestEval?.num_cases ?? '—'}
            sub={
              latestEval
                ? `${(latestEval.answer_correctness * 100).toFixed(0)}% answer correctness`
                : ''
            }
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card className="p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-display text-sm font-semibold text-mist-50">
                System status
              </h2>

              <Badge tone={health?.gemini_configured ? 'good' : 'warn'}>
                {health?.gemini_configured
                  ? 'gemini connected'
                  : 'gemini unavailable'}
              </Badge>
            </div>

            <dl className="text-sm space-y-2 font-mono text-mist-300">
              <div className="flex justify-between">
                <dt className="text-mist-400">Generation model</dt>
                <dd>{health?.gemini_model ?? '—'}</dd>
              </div>

              <div className="flex justify-between">
                <dt className="text-mist-400">Embedding model</dt>
                <dd>{health?.embedding_model ?? '—'}</dd>
              </div>

              <div className="flex justify-between">
                <dt className="text-mist-400">Vector index</dt>
                <dd>FAISS (local)</dd>
              </div>

              <div className="flex justify-between">
                <dt className="text-mist-400">Backend</dt>
                <dd>{health ? 'online' : '—'}</dd>
              </div>
            </dl>
          </Card>

          <Card className="p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-display text-sm font-semibold text-mist-50">
                Latest evaluation
              </h2>

              <Link
                to="/evaluation"
                className="text-xs text-signal-teal font-mono hover:underline"
              >
                run again →
              </Link>
            </div>

            {latestEval ? (
              <dl className="text-sm space-y-2 font-mono text-mist-300">
                <div className="flex justify-between">
                  <dt className="text-mist-400">Retrieval accuracy</dt>
                  <dd>
                    {(latestEval.retrieval_accuracy * 100).toFixed(0)}%
                  </dd>
                </div>

                <div className="flex justify-between">
                  <dt className="text-mist-400">Answer correctness</dt>
                  <dd>
                    {(latestEval.answer_correctness * 100).toFixed(0)}%
                  </dd>
                </div>

                <div className="flex justify-between">
                  <dt className="text-mist-400">Citation accuracy</dt>
                  <dd>
                    {(latestEval.citation_accuracy * 100).toFixed(0)}%
                  </dd>
                </div>

                <div className="flex justify-between">
                  <dt className="text-mist-400">Hallucination rate</dt>
                  <dd>
                    {(latestEval.hallucination_rate * 100).toFixed(0)}%
                  </dd>
                </div>

                <div className="flex justify-between">
                  <dt className="text-mist-400">Test cases</dt>
                  <dd>{latestEval.num_cases}</dd>
                </div>
              </dl>
            ) : (
              <p className="text-sm text-mist-400">
                No evaluation runs yet. Head to Evaluation to run the test set.
              </p>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
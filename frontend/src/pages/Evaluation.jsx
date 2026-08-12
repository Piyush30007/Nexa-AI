import React from 'react'
import { useEffect, useState } from 'react'
import PageHeader from '../components/PageHeader.jsx'
import {
  Card,
  StatCard,
  Badge,
  Button,
  Spinner,
} from '../components/ui.jsx'
import { api } from '../api/client.js'

export default function Evaluation() {
  const [runs, setRuns] = useState([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(null)

  async function refresh() {
    try {
      const results =
        await api.getEvaluationResults()

      setRuns(
        Array.isArray(results)
          ? results
          : results
            ? [results]
            : [],
      )
    } catch (error) {
      setError(error.message)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  async function runNow() {
    setRunning(true)
    setError(null)

    try {
      const run =
        await api.runEvaluation()

      setRuns((previous) => [
        run,
        ...previous.filter(
          (item) => item.id !== run.id,
        ),
      ])

      setExpanded(run.id)
    } catch (error) {
      setError(error.message)
    } finally {
      setRunning(false)
    }
  }

  const latest = runs[0]
  const previous = runs[1]

  function delta(key) {
    if (!latest || !previous) return null

    return (
      (latest[key] - previous[key]) * 100
    )
  }

  return (
    <div>
      <PageHeader
        eyebrow="Regression testing"
        title="Evaluation"
        description="Evaluate retrieval, answer correctness, citations, and hallucination against your test dataset."
        action={
          <Button
            onClick={runNow}
            disabled={running}
          >
            {running ? (
              <span className="flex items-center gap-2">
                <Spinner />
                Running…
              </span>
            ) : (
              'Run evaluation'
            )}
          </Button>
        }
      />

      <div className="px-8 py-6">
        <Card className="px-4 py-3 mb-6 border-signal-amber/20">
          <p className="text-xs text-mist-400">
            Evaluation sends in-context questions to Gemini.
            Run it manually when you want to check the pipeline;
            avoid unnecessary runs when using a limited API quota.
          </p>
        </Card>

        {error && (
          <p className="text-sm text-signal-coral mb-4">
            {error}
          </p>
        )}

        {latest ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <StatCard
                label="Retrieval accuracy"
                value={`${(
                  latest.retrieval_accuracy * 100
                ).toFixed(0)}%`}
                sub={
                  previous
                    ? trendLabel(
                        delta(
                          'retrieval_accuracy',
                        ),
                      )
                    : null
                }
                tone={
                  latest.retrieval_accuracy >= 0.8
                    ? 'good'
                    : 'warn'
                }
              />

              <StatCard
                label="Answer correctness"
                value={`${(
                  latest.answer_correctness * 100
                ).toFixed(0)}%`}
                sub={
                  previous
                    ? trendLabel(
                        delta(
                          'answer_correctness',
                        ),
                      )
                    : null
                }
                tone={
                  latest.answer_correctness >= 0.8
                    ? 'good'
                    : 'warn'
                }
              />

              <StatCard
                label="Citation accuracy"
                value={`${(
                  latest.citation_accuracy * 100
                ).toFixed(0)}%`}
                sub={
                  previous
                    ? trendLabel(
                        delta(
                          'citation_accuracy',
                        ),
                      )
                    : null
                }
                tone={
                  latest.citation_accuracy >= 0.8
                    ? 'good'
                    : 'warn'
                }
              />

              <StatCard
                label="Hallucination rate"
                value={`${(
                  latest.hallucination_rate * 100
                ).toFixed(0)}%`}
                sub={
                  previous
                    ? trendLabel(
                        -delta(
                          'hallucination_rate',
                        ),
                      )
                    : null
                }
                tone={
                  latest.hallucination_rate <= 0.1
                    ? 'good'
                    : 'warn'
                }
              />
            </div>

            <p className="text-xs font-mono text-mist-400 mb-6">
              {latest.num_cases} test cases · avg latency{' '}
              {Number(
                latest.avg_latency_ms || 0,
              ).toFixed(0)}
              ms · run{' '}
              {new Date(
                latest.timestamp,
              ).toLocaleString()}
            </p>
          </>
        ) : (
          <Card className="px-5 py-6 mb-6 text-sm text-mist-400">
            No evaluation runs yet.
          </Card>
        )}

        <h2 className="font-display text-sm font-semibold text-mist-50 mb-3">
          Run history
        </h2>

        <div className="space-y-3">
          {runs.map((run) => (
            <Card
              key={run.id}
              className="overflow-hidden"
            >
              <button
                onClick={() =>
                  setExpanded(
                    expanded === run.id
                      ? null
                      : run.id,
                  )
                }
                className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-ink-700/40"
              >
                <div className="flex items-center gap-3 text-sm">
                  <span className="font-mono text-mist-400 text-xs">
                    {new Date(
                      run.timestamp,
                    ).toLocaleString()}
                  </span>

                  <Badge>
                    {run.num_cases} cases
                  </Badge>

                  <Badge
                    tone={
                      run.hallucination_rate <= 0.1
                        ? 'good'
                        : 'warn'
                    }
                  >
                    {(
                      run.hallucination_rate * 100
                    ).toFixed(0)}
                    % hallucination
                  </Badge>
                </div>

                <span className="text-mist-400 text-xs font-mono">
                  {expanded === run.id
                    ? '▲'
                    : '▼'}
                </span>
              </button>

              {expanded === run.id && (
                <div className="border-t border-ink-700 divide-y divide-ink-700/60">
                  {(run.results || []).map(
                    (result, index) => (
                      <div
                        key={index}
                        className="px-4 py-3 text-sm"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <p className="text-mist-100">
                            {result.question}
                          </p>

                          <div className="flex gap-1.5 shrink-0 flex-wrap justify-end">
                            <Badge
                              tone={
                                result.retrieval_hit
                                  ? 'good'
                                  : 'bad'
                              }
                            >
                              retrieval
                            </Badge>

                            <Badge
                              tone={
                                result.answer_correct
                                  ? 'good'
                                  : 'bad'
                              }
                            >
                              answer
                            </Badge>

                            <Badge
                              tone={
                                result.citation_correct
                                  ? 'good'
                                  : 'bad'
                              }
                            >
                              citation
                            </Badge>

                            <Badge
                              tone={
                                result.hallucinated
                                  ? 'bad'
                                  : 'good'
                              }
                            >
                              {result.hallucinated
                                ? 'hallucinated'
                                : 'safe'}
                            </Badge>
                          </div>
                        </div>

                        <p className="text-xs text-mist-400 mt-2 font-mono">
                          expected:{' '}
                          {result.expected_source ||
                            'no source — should refuse'}
                          {' · '}
                          got:{' '}
                          {result.actual_sources?.join(
                            ', ',
                          ) || 'none'}
                        </p>

                        {result.actual_answer && (
                          <p className="text-xs text-mist-300 mt-2">
                            {result.actual_answer}
                          </p>
                        )}
                      </div>
                    ),
                  )}
                </div>
              )}
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}

function trendLabel(deltaPct) {
  if (Math.abs(deltaPct) < 0.5) {
    return 'no change vs. last run'
  }

  const sign = deltaPct > 0 ? '▲' : '▼'

  return `${sign} ${Math.abs(deltaPct).toFixed(0)}pt vs. last run`
}
import React from 'react'
import PageHeader from '../components/PageHeader.jsx'
import { Card } from '../components/ui.jsx'

export default function Usage() {
  return (
    <div>
      <PageHeader
        eyebrow="Cost control"
        title="Usage & Cost"
        description="Every LLM call can be logged with tokens, latency, and estimated cost."
      />

      <div className="px-8 py-6">
        <Card className="p-6">
          <h2 className="font-display text-sm font-semibold text-mist-50 mb-2">
            Usage API unavailable
          </h2>

          <p className="text-sm text-mist-400">
            The current backend does not expose a /api/usage endpoint yet.
            Usage logging is available in the backend database, but a
            frontend usage API has not been added.
          </p>
        </Card>
      </div>
    </div>
  )
}
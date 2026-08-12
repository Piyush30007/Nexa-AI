import React from 'react'
import { Badge } from './ui.jsx'

export default function SourceReceipt({
  sources,
  grounded,
}) {
  if (!grounded || !sources?.length) {
    return (
      <div className="mt-3 border border-dashed border-ink-600 rounded-md bg-ink-900/60 px-3 py-2.5">
        <div className="flex items-center gap-2">
          <Badge tone="warn">
            ungrounded
          </Badge>

          <span className="text-[10px] font-mono text-mist-400">
            No matching evidence was retrieved
          </span>
        </div>
      </div>
    )
  }

  return (
    <div className="mt-3 border border-dashed border-ink-600 rounded-md bg-ink-900/60 px-3 py-2.5">
      <div className="text-[10px] font-mono uppercase tracking-[0.12em] text-mist-400 mb-2 flex items-center gap-1.5">
        <span className="text-signal-teal">
          ✓
        </span>

        grounded — {sources.length} source
        {sources.length > 1 ? 's' : ''}
      </div>

      <ul className="space-y-1.5">
        {sources.map((source) => (
          <li
            key={source.chunk_id}
            className="flex items-center justify-between text-xs font-mono text-mist-300 gap-3"
          >
            <span className="truncate">
              📄 {source.document}

              {source.page != null && (
                <span className="text-mist-400">
                  {' '}
                  — p.{source.page}
                </span>
              )}
            </span>

            <span className="text-mist-400 shrink-0">
              match {(source.score * 100).toFixed(0)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
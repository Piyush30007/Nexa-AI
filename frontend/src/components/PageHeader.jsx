import React from 'react'

export default function PageHeader({ eyebrow, title, description, action }) {
  return (
    <header className="border-b border-ink-700 px-8 py-6">
      <div className="flex items-start justify-between gap-6">
        <div>
          {eyebrow && (
            <div className="text-[11px] font-mono uppercase tracking-[0.12em] text-signal-teal mb-2">
              {eyebrow}
            </div>
          )}

          <h1 className="font-display text-2xl font-semibold text-mist-50">
            {title}
          </h1>

          {description && (
            <p className="text-sm text-mist-400 mt-2 max-w-2xl">
              {description}
            </p>
          )}
        </div>

        {action && (
          <div className="shrink-0">
            {action}
          </div>
        )}
      </div>
    </header>
  )
}
import React from 'react'

export default function PageHeader({ eyebrow, title, description, action }) {
  return (
    <header className="bg-white border-b border-slate-200 px-6 sm:px-8 py-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          {eyebrow && (
            <div className="text-xs font-semibold uppercase tracking-wider text-blue-600 mb-1">
              {eyebrow}
            </div>
          )}

          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            {title}
          </h1>

          {description && (
            <p className="text-sm text-slate-500 mt-1 max-w-3xl">
              {description}
            </p>
          )}
        </div>

        {action && (
          <div className="shrink-0 flex items-center gap-2">
            {action}
          </div>
        )}
      </div>
    </header>
  )
}
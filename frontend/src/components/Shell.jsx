import React from 'react'
import { NavLink } from 'react-router-dom'

export default function Shell({ children }) {
  const links = [
    { to: '/', label: 'Dashboard' },
    { to: '/assistant', label: 'AI Assistant' },
    { to: '/knowledge-base', label: 'Knowledge Base' },
    { to: '/evaluation', label: 'Evaluation' },
    { to: '/usage', label: 'Usage' },
    { to: '/settings', label: 'Settings' },
  ]

  return (
    <div className="min-h-screen bg-ink-950 text-mist-100 flex">
      <aside className="w-60 shrink-0 border-r border-ink-700 bg-ink-900 min-h-screen">
        <div className="px-5 py-6 border-b border-ink-700">
          <h1 className="font-display text-xl font-semibold text-mist-50">
            Nexa AI
          </h1>

          <p className="text-xs text-mist-400 mt-1">
            Knowledge Assistant
          </p>
        </div>

        <nav className="p-3 space-y-1">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === '/'}
              className={({ isActive }) =>
                `block px-3 py-2.5 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-signal-teal/10 text-signal-teal border border-signal-teal/20'
                    : 'text-mist-300 hover:bg-ink-800 hover:text-mist-50'
                }`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="flex-1 min-w-0 min-h-screen">
        {children}
      </main>
    </div>
  )
}
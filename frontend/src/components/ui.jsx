import React from 'react'
export function Card({ children, className = '' }) {
  return (
    <div className={`bg-ink-800 border border-ink-700 rounded-lg shadow-panel ${className}`}>{children}</div>
  )
}

export function StatCard({ label, value, sub, tone = 'default' }) {
  const toneColor =
    tone === 'good' ? 'text-signal-teal' : tone === 'warn' ? 'text-signal-amber' : 'text-mist-50'
  return (
    <Card className="px-5 py-4">
      <div className="text-[11px] font-mono uppercase tracking-[0.1em] text-mist-400">{label}</div>
      <div className={`font-display text-2xl font-semibold mt-1.5 ${toneColor}`}>{value}</div>
      {sub && <div className="text-xs text-mist-400 mt-1">{sub}</div>}
    </Card>
  )
}

export function Badge({ children, tone = 'default' }) {
  const tones = {
    default: 'bg-ink-700 text-mist-300 border-ink-600',
    good: 'bg-signal-teal/10 text-signal-teal border-signal-teal/30',
    warn: 'bg-signal-amber/10 text-signal-amber border-signal-amber/30',
    bad: 'bg-signal-coral/10 text-signal-coral border-signal-coral/30',
  }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-sm text-[11px] font-mono border ${tones[tone]}`}>
      {children}
    </span>
  )
}

export function Spinner({ className = '' }) {
  return (
    <div
      className={`w-4 h-4 border-2 border-mist-500/30 border-t-signal-teal rounded-full animate-spin ${className}`}
    />
  )
}

export function Button({ children, variant = 'primary', className = '', ...props }) {
  const variants = {
    primary: 'bg-signal-teal text-ink-950 hover:bg-signal-teal/90 font-medium',
    ghost: 'bg-transparent text-mist-200 border border-ink-600 hover:bg-ink-700',
    danger: 'bg-transparent text-signal-coral border border-signal-coral/40 hover:bg-signal-coral/10',
  }
  return (
    <button
      className={`px-4 py-2 rounded-md text-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

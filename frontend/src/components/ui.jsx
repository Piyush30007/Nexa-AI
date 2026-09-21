import React from 'react'

export function Card({ children, className = '' }) {
  return (
    <div className={`bg-white border border-slate-200 rounded-xl shadow-xs ${className}`}>
      {children}
    </div>
  )
}

export function StatCard({ label, value, sub, tone = 'default' }) {
  const toneClasses = {
    default: 'text-slate-900',
    blue: 'text-blue-600',
    orange: 'text-orange-600',
    purple: 'text-purple-600',
    good: 'text-blue-600',
    warn: 'text-orange-600',
    bad: 'text-red-600',
  }

  return (
    <Card className="p-5">
      <div className="text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</div>
      <div className={`font-semibold text-2xl tracking-tight mt-1.5 ${toneClasses[tone] || toneClasses.default}`}>
        {value}
      </div>
      {sub && <div className="text-xs text-slate-500 mt-1">{sub}</div>}
    </Card>
  )
}

export function Badge({ children, tone = 'default', className = '' }) {
  const tones = {
    default: 'bg-slate-100 text-slate-700 border-slate-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    good: 'bg-blue-50 text-blue-700 border-blue-200',
    orange: 'bg-orange-50 text-orange-700 border-orange-200',
    warn: 'bg-orange-50 text-orange-700 border-orange-200',
    purple: 'bg-purple-50 text-purple-700 border-purple-200',
    bad: 'bg-red-50 text-red-700 border-red-200',
  }

  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium border ${
        tones[tone] || tones.default
      } ${className}`}
    >
      {children}
    </span>
  )
}

export function Spinner({ className = 'w-4 h-4' }) {
  return (
    <div
      className={`border-2 border-slate-200 border-t-blue-600 rounded-full animate-spin shrink-0 ${className}`}
    />
  )
}

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  className = '',
  icon: Icon,
  ...props
}) {
  const variants = {
    primary:
      'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800 shadow-xs border border-blue-600 font-medium',
    secondary:
      'bg-white text-slate-700 hover:bg-slate-50 active:bg-slate-100 border border-slate-200 shadow-xs font-medium',
    ghost:
      'bg-transparent text-slate-600 hover:bg-slate-100 hover:text-slate-900 active:bg-slate-200 font-medium',
    danger:
      'bg-white text-red-600 hover:bg-red-50 active:bg-red-100 border border-red-200 font-medium',
  }

  const sizes = {
    sm: 'px-2.5 py-1.5 text-xs rounded-lg gap-1.5',
    md: 'px-3.5 py-2 text-sm rounded-lg gap-2',
    lg: 'px-5 py-2.5 text-base rounded-xl gap-2.5',
  }

  const iconSizes = {
    sm: 'w-3.5 h-3.5 shrink-0',
    md: 'w-4 h-4 shrink-0',
    lg: 'w-5 h-5 shrink-0',
  }

  return (
    <button
      className={`inline-flex items-center justify-center transition-colors select-none disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-auto cursor-pointer ${
        sizes[size] || sizes.md
      } ${variants[variant] || variants.primary} ${className}`}
      {...props}
    >
      {Icon && (
        typeof Icon === 'function' ? (
          <Icon className={iconSizes[size] || 'w-4 h-4 shrink-0'} />
        ) : (
          Icon
        )
      )}
      {children}
    </button>
  )
}

export function MetricCard({
  icon: Icon,
  iconColor = 'blue',
  label,
  value,
  subtitle,
  trend,
  trendUp = true,
}) {
  const iconColorStyles = {
    blue: 'bg-blue-50 text-blue-600 border-blue-100',
    orange: 'bg-orange-50 text-orange-600 border-orange-100',
    purple: 'bg-purple-50 text-purple-600 border-purple-100',
    gray: 'bg-slate-100 text-slate-600 border-slate-200',
  }

  return (
    <Card className="p-3.5 sm:p-4 flex items-center gap-3 sm:gap-3.5 hover:border-slate-300 transition-colors min-w-0 overflow-hidden">
      {Icon && (
        <div
          className={`w-9 h-9 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center shrink-0 border ${
            iconColorStyles[iconColor] || iconColorStyles.blue
          }`}
        >
          <Icon className="w-4.5 h-4.5 sm:w-5 sm:h-5 shrink-0" />
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="text-xs font-medium text-slate-500 truncate">{label}</div>
        <div className="flex items-baseline gap-2 mt-0.5 min-w-0">
          <span className="text-xl font-bold text-slate-900 tracking-tight truncate">{value}</span>
          {trend && (
            <span
              className={`text-[11px] font-semibold flex items-center gap-0.5 ${
                trendUp ? 'text-blue-600' : 'text-orange-600'
              }`}
            >
              {trendUp ? '▲' : '▼'} {trend}
            </span>
          )}
        </div>
        {subtitle && <div className="text-[11px] text-slate-500 mt-0.5 truncate">{subtitle}</div>}
      </div>
    </Card>
  )
}

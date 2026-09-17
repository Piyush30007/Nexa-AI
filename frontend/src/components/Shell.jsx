import React, { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  NexaLogo,
  DashboardIcon,
  AssistantIcon,
  KnowledgeIcon,
  EvaluationIcon,
  UsageIcon,
  SettingsIcon,
  SearchIcon,
  BellIcon,
  ChevronDownIcon,
} from './Icons.jsx'

export default function Shell({ children }) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const location = useLocation()

  const navLinks = [
    { to: '/', label: 'Dashboard', icon: DashboardIcon, exact: true },
    { to: '/assistant', label: 'AI Assistant', icon: AssistantIcon },
    { to: '/knowledge-base', label: 'Knowledge Base', icon: KnowledgeIcon },
    { to: '/evaluation', label: 'Evaluation', icon: EvaluationIcon },
    { to: '/usage', label: 'Usage & Analytics', icon: UsageIcon },
    { to: '/settings', label: 'Settings', icon: SettingsIcon },
  ]

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex">
      {/* ======================================================
          SIDEBAR
          ====================================================== */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 bg-white border-r border-slate-200 flex flex-col justify-between transition-transform duration-200 lg:translate-x-0 ${
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div>
          {/* Brand Header */}
          <div className="px-5 py-5 border-b border-slate-100 flex items-center gap-3">
            <NexaLogo className="w-8 h-8 shrink-0" />
            <div className="min-w-0">
              <div className="font-bold text-base text-slate-900 tracking-tight flex items-center gap-1.5">
                Nexa AI
              </div>
              <div className="text-[11px] text-slate-500 font-medium truncate">
                Enterprise Knowledge Assistant
              </div>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-3 space-y-1">
            {navLinks.map((link) => {
              const Icon = link.icon
              const isActive = link.exact
                ? location.pathname === link.to
                : location.pathname.startsWith(link.to)

              return (
                <NavLink
                  key={link.to}
                  to={link.to}
                  end={link.exact}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-blue-50 text-blue-600 font-semibold shadow-xs'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-blue-600' : 'text-slate-500'}`} />
                  <span className="truncate">{link.label}</span>
                </NavLink>
              )
            })}
          </nav>
        </div>

        {/* Bottom Version Card */}
        <div className="p-4 border-t border-slate-100">
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5">
            <div className="flex items-center gap-2 mb-1.5">
              <NexaLogo className="w-5 h-5 shrink-0" />
              <div className="font-semibold text-xs text-slate-900">Nexa AI Enterprise</div>
            </div>
            <div className="flex items-center gap-1.5 text-[11px] text-slate-500 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 inline-block" />
              <span>V2.0.0</span>
            </div>
            <p className="text-[11px] text-slate-500 mt-2 leading-relaxed font-normal">
              Grounded Answers. Safer Decisions. Real Business Impact.
            </p>
          </div>
        </div>
      </aside>

      {/* Overlay for mobile drawer */}
      {mobileMenuOpen && (
        <div
          onClick={() => setMobileMenuOpen(false)}
          className="fixed inset-0 z-30 bg-slate-900/20 backdrop-blur-xs lg:hidden"
        />
      )}

      {/* ======================================================
          MAIN WORKSPACE
          ====================================================== */}
      <div className="flex-1 lg:pl-64 flex flex-col min-w-0 min-h-screen">
        {/* Top Header */}
        <header className="sticky top-0 z-20 h-16 bg-white border-b border-slate-200 px-4 sm:px-8 flex items-center justify-between gap-4">
          {/* Mobile Menu Button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="lg:hidden p-2 text-slate-600 hover:bg-slate-100 rounded-lg"
            aria-label="Toggle Navigation"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          {/* Center Search Input */}
          <div className="flex-1 max-w-xl mx-auto hidden sm:block">
            <div className="relative flex items-center">
              <SearchIcon className="absolute left-3.5 w-4 h-4 text-slate-400 pointer-events-none" />
              <input
                type="text"
                placeholder="Search documents, ask anything..."
                className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-10 pr-16 py-1.5 text-sm text-slate-900 placeholder:text-slate-400 focus:bg-white focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-none transition-all"
              />
              <div className="absolute right-3 flex items-center gap-0.5 pointer-events-none">
                <kbd className="text-[10px] font-mono font-medium text-slate-400 bg-white border border-slate-200 px-1.5 py-0.5 rounded shadow-2xs">
                  Ctrl K
                </kbd>
              </div>
            </div>
          </div>

          {/* Right Header Status & Profile */}
          <div className="flex items-center gap-4 ml-auto">
            {/* System Status */}
            <div className="hidden md:flex items-center gap-2.5 px-3 py-1 bg-slate-50 border border-slate-200 rounded-full">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-600" />
              </span>
              <div className="text-left">
                <div className="text-xs font-semibold text-slate-800 leading-tight">System Online</div>
                <div className="text-[10px] text-slate-500 font-normal leading-tight">All services operational</div>
              </div>
            </div>

            {/* Notification Bell */}
            <button
              className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors relative"
              title="Notifications"
            >
              <BellIcon className="w-4 h-4" />
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-blue-600 rounded-full" />
            </button>

            {/* User Profile */}
            <div className="flex items-center gap-2.5 pl-2 border-l border-slate-200 cursor-pointer">
              <div className="w-8 h-8 rounded-full bg-blue-600 text-white font-semibold text-sm flex items-center justify-center shadow-xs">
                P
              </div>
              <div className="hidden sm:block text-left">
                <div className="text-xs font-semibold text-slate-900 leading-tight">Piyush Singh</div>
                <div className="text-[10px] text-slate-500 font-normal leading-tight">Admin</div>
              </div>
              <ChevronDownIcon className="w-3.5 h-3.5 text-slate-400 hidden sm:block" />
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 min-w-0 bg-slate-50">
          {children}
        </main>
      </div>
    </div>
  )
}
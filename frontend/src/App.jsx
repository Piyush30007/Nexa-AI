import React from 'react'
import { Routes, Route } from 'react-router-dom'
import Shell from './components/Shell.jsx'
import Dashboard from './pages/Dashboard.jsx'
import AIAssistant from './pages/AIAssistant.jsx'
import KnowledgeBase from './pages/KnowledgeBase.jsx'
import Evaluation from './pages/Evaluation.jsx'
import Usage from './pages/Usage.jsx'
import Settings from './pages/Settings.jsx'

export default function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/assistant" element={<AIAssistant />} />
        <Route path="/knowledge-base" element={<KnowledgeBase />} />
        <Route path="/evaluation" element={<Evaluation />} />
        <Route path="/usage" element={<Usage />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Shell>
  )
}

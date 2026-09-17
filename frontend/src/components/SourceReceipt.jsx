import React, { useState } from 'react'
import { Card, Badge, Button } from './ui.jsx'
import { PdfIcon, FileTextIcon, ExternalLinkIcon, XIcon } from './Icons.jsx'

export default function SourceReceipt({ sources = [], grounded = true }) {
  const [modalOpen, setModalOpen] = useState(false)

  if (!sources || sources.length === 0) {
    return (
      <Card className="p-4 bg-white border border-slate-200 shadow-xs">
        <div className="font-bold text-sm text-slate-900 mb-2">Sources (0)</div>
        <div className="text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-lg p-3 text-center">
          {grounded ? 'No external source citations.' : 'Evidence bounded / No document match found.'}
        </div>
      </Card>
    )
  }

  // Primary featured source
  const primarySource = sources[0]
  const docTitle =
    primarySource.document?.replace(/\.[^/.]+$/, '').replace(/_/g, ' ') ||
    'Document'
  const filename = primarySource.document || 'document'
  const relevance =
    primarySource.score != null
      ? `${(primarySource.score * 100).toFixed(1)}%`
      : primarySource.rerank_score != null
      ? `${(primarySource.rerank_score * 100).toFixed(1)}%`
      : null
  const quoteText = primarySource.text || primarySource.content || ''
  const pageNum = primarySource.page != null ? `Page ${primarySource.page}` : null
  const chunkNum = primarySource.chunk_id ? `Chunk ${String(primarySource.chunk_id).slice(-4)}` : null

  return (
    <>
      <Card className="p-4 bg-white border border-slate-200 shadow-xs">
        {/* Header */}
        <div className="font-bold text-sm text-slate-900 mb-3 flex items-center justify-between">
          <span>Sources ({sources.length})</span>
          {sources.length > 1 && (
            <span className="text-xs text-blue-600 font-medium">+{sources.length - 1} more</span>
          )}
        </div>

        {/* Primary Evidence Card */}
        <div className="border border-slate-200 rounded-xl p-3 bg-white hover:border-slate-300 transition-colors">
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2.5 min-w-0">
              <PdfIcon className="w-8 h-8 shrink-0" />
              <div className="min-w-0">
                <div className="font-semibold text-xs text-slate-900 capitalize truncate">
                  {docTitle}
                </div>
                <div className="text-[11px] text-slate-400 font-mono truncate">{filename}</div>
              </div>
            </div>
            {relevance && (
              <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-600 border border-blue-100 shrink-0">
                {relevance}
              </span>
            )}
          </div>

          {/* Snippet quote */}
          {quoteText && (
            <div className="mt-2.5 p-2.5 bg-slate-50 border border-slate-100 rounded-lg text-xs text-slate-600 font-normal leading-relaxed italic line-clamp-3">
              "{quoteText}"
            </div>
          )}

          {/* Footer metadata */}
          {(pageNum || chunkNum) && (
            <div className="mt-2 text-[11px] font-mono text-slate-400 flex items-center gap-2">
              {pageNum && <span>{pageNum}</span>}
              {pageNum && chunkNum && <span>•</span>}
              {chunkNum && <span>{chunkNum}</span>}
            </div>
          )}
        </div>

        {/* View All Sources Button */}
        <button
          onClick={() => setModalOpen(true)}
          className="mt-3 w-full py-2 px-3 rounded-lg border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-50 active:bg-slate-100 flex items-center justify-center gap-2 transition-colors cursor-pointer"
        >
          <FileTextIcon className="w-3.5 h-3.5 text-slate-500" />
          <span>View all sources</span>
        </button>
      </Card>

      {/* Sources Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/30 backdrop-blur-xs">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xl max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="font-bold text-base text-slate-900">
                  Retrieved Source Documents ({sources.length})
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Official evidence chunks used to synthesize this answer
                </p>
              </div>
              <button
                onClick={() => setModalOpen(false)}
                className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100"
              >
                <XIcon className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-4">
              {sources.map((src, i) => (
                <div key={src.chunk_id || i} className="border border-slate-200 rounded-xl p-4 bg-slate-50/50">
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <PdfIcon className="w-6 h-6" />
                      <span className="font-semibold text-xs text-slate-800">
                        {src.document || 'Document'}
                      </span>
                    </div>
                    {src.score != null && (
                      <Badge tone="blue">
                        Match {(src.score * 100).toFixed(1)}%
                      </Badge>
                    )}
                  </div>
                  <div className="text-xs text-slate-700 leading-relaxed bg-white border border-slate-200 rounded-lg p-3 whitespace-pre-wrap font-sans">
                    {src.text || src.content || 'No text content available'}
                  </div>
                  <div className="mt-2 text-[11px] font-mono text-slate-400 flex items-center gap-3">
                    {src.page != null && <span>Page: {src.page}</span>}
                    {src.chunk_id != null && <span>Chunk ID: {src.chunk_id}</span>}
                  </div>
                </div>
              ))}
            </div>

            <div className="px-6 py-3.5 bg-slate-50 border-t border-slate-200 flex justify-end">
              <Button variant="secondary" size="sm" onClick={() => setModalOpen(false)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
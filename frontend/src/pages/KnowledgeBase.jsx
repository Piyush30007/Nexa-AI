import React, { useRef, useState, useEffect } from 'react'
import PageHeader from '../components/PageHeader.jsx'
import { Card, Badge, Button, Spinner } from '../components/ui.jsx'
import {
  FileTextIcon,
  PdfIcon,
  PlusIcon,
  CheckCircleFilled,
  SearchIcon,
  TrashIcon,
} from '../components/Icons.jsx'
import { api } from '../api/client.js'

export default function KnowledgeBase() {
  const [docs, setDocs] = useState(() => {
    try {
      const saved = localStorage.getItem('nexa_indexed_documents')
      return saved ? JSON.parse(saved) : []
    } catch {
      return []
    }
  })

  const [searchFilter, setSearchFilter] = useState('')
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [dragOver, setDragOver] = useState(false)

  const fileInput = useRef(null)

  // Persist documents list to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('nexa_indexed_documents', JSON.stringify(docs))
    } catch (err) {
      console.error('Failed to save documents to localStorage:', err)
    }
  }, [docs])

  async function handleFiles(files) {
    setError(null)

    const validFiles = Array.from(files).filter((file) =>
      /\.(pdf|docx|txt)$/i.test(file.name)
    )

    if (!validFiles.length) {
      setError('Please upload a PDF, DOCX, or TXT file.')
      return
    }

    for (const file of validFiles) {
      setUploading(true)

      try {
        const response = await api.uploadDocument(file)
        const uploadedDoc = response?.document || response || {}

        const newDoc = {
          id: uploadedDoc.id || crypto.randomUUID(),
          filename: uploadedDoc.filename || file.name,
          title: file.name.replace(/\.[^/.]+$/, '').replace(/_/g, ' '),
          file_type: uploadedDoc.file_type || file.name.split('.').pop(),
          num_chunks: uploadedDoc.num_chunks ?? 1,
          status: 'Indexed',
          uploaded_at: new Date().toISOString(),
          file_size: `${(file.size / 1024).toFixed(0)} KB`,
        }

        setDocs((prev) => [newDoc, ...prev.filter((d) => d.filename !== newDoc.filename)])
      } catch (err) {
        console.error('Upload error:', err)
        setError(`Failed to index ${file.name}: ${err.message}`)
      } finally {
        setUploading(false)
      }
    }
  }

  function removeDoc(id) {
    setDocs((prev) => prev.filter((d) => d.id !== id))
  }

  const filteredDocs = docs.filter((d) =>
    (d.filename + d.title).toLowerCase().includes(searchFilter.toLowerCase())
  )

  return (
    <div>
      <PageHeader
        eyebrow="Document Management"
        title="Knowledge Base"
        description="Enterprise documents indexed into Qdrant vector database with Gemini embeddings."
        action={
          <Button
            variant="primary"
            size="md"
            icon={PlusIcon}
            onClick={() => fileInput.current?.click()}
            disabled={uploading}
          >
            {uploading ? 'Indexing...' : 'Upload Document'}
          </Button>
        }
      />

      <div className="px-6 sm:px-8 py-6 space-y-6 max-w-7xl mx-auto">
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center justify-between">
            <span>⚠ {error}</span>
            <button onClick={() => setError(null)} className="text-red-500 hover:text-red-800 text-xs">
              Dismiss
            </button>
          </div>
        )}

        {/* Upload Drag & Drop Area */}
        <div
          onDragOver={(e) => {
            e.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragOver(false)
            if (e.dataTransfer.files) handleFiles(e.dataTransfer.files)
          }}
          onClick={() => fileInput.current?.click()}
          className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
            dragOver
              ? 'border-blue-500 bg-blue-50/50'
              : 'border-slate-200 bg-white hover:border-blue-400 hover:bg-slate-50/50'
          }`}
        >
          <input
            type="file"
            ref={fileInput}
            onChange={(e) => e.target.files && handleFiles(e.target.files)}
            className="hidden"
            multiple
            accept=".pdf,.docx,.txt"
          />

          <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 border border-blue-100 flex items-center justify-center mx-auto mb-3">
            {uploading ? <Spinner className="w-5 h-5 border-blue-600" /> : <FileTextIcon className="w-6 h-6" />}
          </div>

          <div className="font-bold text-sm text-slate-900">
            {uploading ? 'Parsing and embedding document...' : 'Click or drag files here to upload'}
          </div>
          <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
            Supports PDF, DOCX, and TXT files. Documents are automatically chunked and stored in Qdrant.
          </p>
        </div>

        {/* Documents Table */}
        <Card className="overflow-hidden">
          {/* Table Header Controls */}
          <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white">
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm text-slate-900">Indexed Documents</span>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-600">
                {docs.length}
              </span>
            </div>

            <div className="relative w-full sm:w-64">
              <SearchIcon className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
              <input
                type="text"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="Filter documents..."
                className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-9 pr-3 py-1.5 text-xs text-slate-900 placeholder:text-slate-400 focus:bg-white focus:border-blue-500 outline-none"
              />
            </div>
          </div>

          {/* Table Body */}
          <div className="overflow-x-auto">
            {filteredDocs.length === 0 ? (
              <div className="p-12 text-center">
                <div className="w-12 h-12 rounded-xl bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
                  <FileTextIcon className="w-6 h-6 text-slate-400" />
                </div>
                <h3 className="font-semibold text-sm text-slate-800">
                  {docs.length === 0 ? 'No documents indexed yet' : 'No matching documents found'}
                </h3>
                <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
                  {docs.length === 0
                    ? 'Upload PDF, DOCX, or TXT files above to index them into your Qdrant vector database.'
                    : 'Try adjusting your search filter.'}
                </p>
              </div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50/80 text-slate-500 font-semibold uppercase tracking-wider border-b border-slate-200 text-[11px]">
                  <tr>
                    <th className="py-3 px-5">Document</th>
                    <th className="py-3 px-5">Chunks</th>
                    <th className="py-3 px-5">Size</th>
                    <th className="py-3 px-5">Status</th>
                    <th className="py-3 px-5">Indexed Date</th>
                    <th className="py-3 px-5 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {filteredDocs.map((doc) => (
                    <tr key={doc.id} className="hover:bg-slate-50/60 transition-colors">
                      <td className="py-3.5 px-5">
                        <div className="flex items-center gap-3">
                          <PdfIcon className="w-7 h-7" />
                          <div>
                            <div className="font-semibold text-slate-900 capitalize">{doc.title}</div>
                            <div className="text-[11px] text-slate-400 font-mono">{doc.filename}</div>
                          </div>
                        </div>
                      </td>
                      <td className="py-3.5 px-5 font-mono text-slate-600">
                        {doc.num_chunks} chunk{doc.num_chunks > 1 ? 's' : ''}
                      </td>
                      <td className="py-3.5 px-5 font-mono text-slate-500">{doc.file_size}</td>
                      <td className="py-3.5 px-5">
                        <span className="inline-flex items-center gap-1 text-xs font-semibold text-blue-700 bg-blue-50 border border-blue-200 px-2.5 py-0.5 rounded-full">
                          <CheckCircleFilled className="w-3 h-3 text-blue-600" />
                          <span>{doc.status}</span>
                        </span>
                      </td>
                      <td className="py-3.5 px-5 text-slate-500">
                        {new Date(doc.uploaded_at).toLocaleDateString()}
                      </td>
                      <td className="py-3.5 px-5 text-right">
                        <button
                          onClick={() => removeDoc(doc.id)}
                          className="p-1 text-slate-400 hover:text-red-600 transition-colors rounded hover:bg-red-50"
                          title="Remove from list"
                        >
                          <TrashIcon className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}
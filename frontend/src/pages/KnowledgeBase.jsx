import React, { useRef, useState } from 'react'
import PageHeader from '../components/PageHeader.jsx'
import {
  Card,
  Badge,
  Button,
  Spinner,
} from '../components/ui.jsx'
import { api } from '../api/client.js'

const STATUS_TONE = {
  ready: 'good',
  processing: 'warn',
  failed: 'bad',
  uploaded: 'good',
}

export default function KnowledgeBase() {
  const [docs, setDocs] = useState([])
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState(null)
  const [dragOver, setDragOver] = useState(false)

  const fileInput = useRef(null)

  async function handleFiles(files) {
    setError(null)

    const validFiles = files.filter((file) =>
      /\.(pdf|docx|txt)$/i.test(file.name),
    )

    if (!validFiles.length) {
      setError('Please upload a PDF, DOCX, or TXT file.')
      return
    }

    for (const file of validFiles) {
      setUploading(true)

      try {
        const response = await api.uploadDocument(file)

        const uploadedDocument = response?.document || response || {}

        const document = {
          id: uploadedDocument.id || crypto.randomUUID(),
          filename: uploadedDocument.filename || file.name,
          file_type:
            uploadedDocument.file_type ||
            file.name.split('.').pop(),
          num_chunks: uploadedDocument.num_chunks ?? 0,
          status: uploadedDocument.status || 'uploaded',
          uploaded_at:
            uploadedDocument.uploaded_at ||
            new Date().toISOString(),
          error_message:
            uploadedDocument.error_message || null,
        }

        setDocs((current) => [document, ...current])
      } catch (error) {
        setError(error.message)
      } finally {
        setUploading(false)
      }
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Ingestion pipeline"
        title="Knowledge Base"
        description="Upload documents to build the searchable knowledge base used by NexaAI."
      />

      <div className="px-8 py-6">
        <div
          onDragOver={(event) => {
            event.preventDefault()
            setDragOver(true)
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(event) => {
            event.preventDefault()
            setDragOver(false)
            handleFiles(Array.from(event.dataTransfer.files))
          }}
          onClick={() => fileInput.current?.click()}
          className={`border-2 border-dashed rounded-lg px-6 py-10 text-center cursor-pointer transition-colors mb-6 ${
            dragOver
              ? 'border-signal-teal/60 bg-signal-teal/5'
              : 'border-ink-600 hover:border-ink-500'
          }`}
        >
          <input
            ref={fileInput}
            type="file"
            accept=".pdf,.docx,.txt"
            multiple
            className="hidden"
            onChange={(event) => {
              handleFiles(Array.from(event.target.files))
              event.target.value = ''
            }}
          />

          {uploading ? (
            <div className="flex items-center justify-center gap-2 text-mist-300">
              <Spinner />
              processing document…
            </div>
          ) : (
            <>
              <p className="text-sm text-mist-200 font-medium">
                Drop a document here, or click to browse
              </p>

              <p className="text-xs text-mist-400 mt-1 font-mono">
                PDF, DOCX, TXT · max 25MB per file
              </p>
            </>
          )}
        </div>

        {error && (
          <Card className="px-4 py-3 mb-4 border-signal-coral/30">
            <p className="text-sm text-signal-coral">
              {error}
            </p>
          </Card>
        )}

        <Card className="overflow-hidden">
          <div className="px-4 py-3 border-b border-ink-700">
            <h2 className="font-display text-sm font-semibold text-mist-50">
              Uploaded documents
            </h2>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] font-mono uppercase tracking-wide text-mist-400 border-b border-ink-700">
                  <th className="px-4 py-3 font-medium">Document</th>
                  <th className="px-4 py-3 font-medium">Type</th>
                  <th className="px-4 py-3 font-medium">Chunks</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Uploaded</th>
                </tr>
              </thead>

              <tbody>
                {docs.length === 0 && (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-4 py-8 text-center text-mist-400"
                    >
                      No documents uploaded in this session — upload one to
                      build the knowledge base.
                    </td>
                  </tr>
                )}

                {docs.map((document) => (
                  <tr
                    key={document.id}
                    className="border-b border-ink-700/60 last:border-0"
                  >
                    <td className="px-4 py-3 text-mist-100">
                      📄 {document.filename}

                      {document.error_message && (
                        <div className="text-xs text-signal-coral mt-1">
                          {document.error_message}
                        </div>
                      )}
                    </td>

                    <td className="px-4 py-3 font-mono text-mist-400 uppercase text-xs">
                      {document.file_type}
                    </td>

                    <td className="px-4 py-3 font-mono text-mist-300">
                      {document.num_chunks}
                    </td>

                    <td className="px-4 py-3">
                      <Badge
                        tone={
                          STATUS_TONE[document.status] || 'default'
                        }
                      >
                        {document.status}
                      </Badge>
                    </td>

                    <td className="px-4 py-3 font-mono text-mist-400 text-xs">
                      {document.uploaded_at
                        ? new Date(
                            document.uploaded_at,
                          ).toLocaleString()
                        : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  )
}
'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Workspace {
  id: string
  name: string
  created_at: string
  phase: string
  therapeutic_area: string
}

export default function WorkbenchPage() {
  const router = useRouter()
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Form state
  const [file, setFile] = useState<File | null>(null)
  const [phase, setPhase] = useState('')
  const [therapeuticArea, setTherapeuticArea] = useState('')
  const [indication, setIndication] = useState('')
  const [dragActive, setDragActive] = useState(false)

  // Fetch existing workspaces
  useEffect(() => {
    fetchWorkspaces()
  }, [])

  const fetchWorkspaces = async () => {
    try {
      const res = await fetch(`${API_URL}/workbench/list`)
      if (res.ok) {
        const data = await res.json()
        setWorkspaces(data.workspaces || [])
      }
    } catch (e) {
      console.error('Failed to fetch workspaces:', e)
    } finally {
      setLoading(false)
    }
  }

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0])
    }
  }, [])

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
    }
  }

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) {
      setError('Please select a protocol file')
      return
    }

    setCreating(true)
    setError(null)

    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('phase', phase)
      formData.append('therapeutic_area', therapeuticArea)
      formData.append('indication', indication)

      const res = await fetch(`${API_URL}/workbench/upload`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to create workspace')
      }

      const workspace = await res.json()
      router.push(`/workbench/${workspace.id}`)
    } catch (e: any) {
      setError(e.message || 'Failed to create workspace')
      setCreating(false)
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">SAP Workbench</h1>
        <p className="mt-2 text-gray-600">
          Section-by-section SAP generation with full traceability
        </p>
      </div>

      {/* Create New Workspace */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Create Study Workspace</h2>

        <form onSubmit={handleCreateWorkspace} className="space-y-6">
          {/* File Upload */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Upload Protocol (PDF, DOCX, TXT)
            </label>
            <div
              className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                dragActive ? 'border-indigo-500 bg-indigo-50' : 'border-gray-300 hover:border-gray-400'
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              {file ? (
                <div className="flex items-center justify-center gap-2">
                  <svg className="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="text-gray-900 font-medium">{file.name}</span>
                  <button
                    type="button"
                    onClick={() => setFile(null)}
                    className="text-gray-400 hover:text-gray-600"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              ) : (
                <div>
                  <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  <p className="mt-2 text-sm text-gray-600">
                    Drag and drop your protocol file, or{' '}
                    <label className="text-indigo-600 hover:text-indigo-500 cursor-pointer">
                      browse
                      <input type="file" className="hidden" onChange={handleFileChange} accept=".pdf,.docx,.doc,.txt" />
                    </label>
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Study Metadata */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Phase</label>
              <select
                value={phase}
                onChange={(e) => setPhase(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="">Select Phase</option>
                <option value="Phase 1">Phase 1</option>
                <option value="Phase 1/2">Phase 1/2</option>
                <option value="Phase 2">Phase 2</option>
                <option value="Phase 2/3">Phase 2/3</option>
                <option value="Phase 3">Phase 3</option>
                <option value="Phase 4">Phase 4</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Therapeutic Area</label>
              <select
                value={therapeuticArea}
                onChange={(e) => setTherapeuticArea(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="">Select Area</option>
                <option value="oncology">Oncology</option>
                <option value="cardiology">Cardiology</option>
                <option value="neurology">Neurology</option>
                <option value="immunology">Immunology</option>
                <option value="infectious_disease">Infectious Disease</option>
                <option value="rare_disease">Rare Disease</option>
                <option value="other">Other</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Indication (Optional)</label>
              <input
                type="text"
                value={indication}
                onChange={(e) => setIndication(e.target.value)}
                placeholder="e.g., NSCLC, Breast Cancer"
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={!file || creating}
            className="w-full bg-indigo-600 text-white py-3 px-4 rounded-md font-medium hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            {creating ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Creating Workspace...
              </span>
            ) : (
              'Create Workspace'
            )}
          </button>
        </form>
      </div>

      {/* Existing Workspaces */}
      <div className="bg-white rounded-lg shadow-sm border p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Recent Workspaces</h2>

        {loading ? (
          <div className="text-center py-8 text-gray-500">Loading...</div>
        ) : workspaces.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No workspaces yet. Create one above to get started.
          </div>
        ) : (
          <div className="divide-y">
            {workspaces.map((ws) => (
              <div
                key={ws.id}
                onClick={() => router.push(`/workbench/${ws.id}`)}
                className="py-4 flex items-center justify-between cursor-pointer hover:bg-gray-50 -mx-4 px-4 transition-colors"
              >
                <div>
                  <h3 className="font-medium text-gray-900">{ws.name}</h3>
                  <p className="text-sm text-gray-500">
                    {ws.phase && <span className="mr-2">{ws.phase}</span>}
                    {ws.therapeutic_area && <span className="capitalize">{ws.therapeutic_area}</span>}
                  </p>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-sm text-gray-400">
                    {new Date(ws.created_at).toLocaleDateString()}
                  </span>
                  <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

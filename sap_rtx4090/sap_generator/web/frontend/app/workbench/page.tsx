'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  Plus,
  Search,
  Filter,
  ChevronRight,
  Upload,
  FileText,
  Clock,
  CheckCircle,
  AlertCircle,
  BarChart3,
  FolderOpen,
  Loader2,
  X,
} from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface Workspace {
  id: string
  name: string
  created_at: string
  phase: string
  therapeutic_area: string
  indication?: string
}

export default function WorkbenchDashboard() {
  const router = useRouter()
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Create modal state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [phase, setPhase] = useState('')
  const [therapeuticArea, setTherapeuticArea] = useState('oncology')
  const [indication, setIndication] = useState('')
  const [dragActive, setDragActive] = useState(false)

  // Filter state
  const [searchQuery, setSearchQuery] = useState('')
  const [phaseFilter, setPhaseFilter] = useState('')

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
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
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

  const resetCreateForm = () => {
    setFile(null)
    setPhase('')
    setTherapeuticArea('oncology')
    setIndication('')
    setError(null)
    setShowCreateModal(false)
  }

  // Filter workspaces
  const filteredWorkspaces = workspaces.filter((ws) => {
    if (phaseFilter && ws.phase !== phaseFilter) return false
    if (searchQuery) {
      const query = searchQuery.toLowerCase()
      if (
        !ws.name.toLowerCase().includes(query) &&
        !ws.indication?.toLowerCase().includes(query) &&
        !ws.therapeutic_area?.toLowerCase().includes(query)
      ) {
        return false
      }
    }
    return true
  })

  // Stats
  const totalWorkspaces = workspaces.length
  const oncologyWorkspaces = workspaces.filter((ws) => ws.therapeutic_area === 'oncology').length

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">SAP Workbench</h1>
              <p className="mt-1 text-gray-500">
                Section-by-section SAP generation with full traceability
              </p>
            </div>
            <button
              onClick={() => setShowCreateModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
            >
              <Plus className="w-5 h-5" />
              New Study
            </button>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-indigo-100 rounded-lg">
                <FolderOpen className="w-5 h-5 text-indigo-600" />
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900">{totalWorkspaces}</div>
                <div className="text-sm text-gray-500">Total Studies</div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <CheckCircle className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900">{oncologyWorkspaces}</div>
                <div className="text-sm text-gray-500">Oncology</div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <BarChart3 className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900">14</div>
                <div className="text-sm text-gray-500">Sections/Study</div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg border p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 rounded-lg">
                <Clock className="w-5 h-5 text-purple-600" />
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900">~2min</div>
                <div className="text-sm text-gray-500">Per Section</div>
              </div>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search studies..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>

          <select
            value={phaseFilter}
            onChange={(e) => setPhaseFilter(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
          >
            <option value="">All Phases</option>
            <option value="Phase 1">Phase 1</option>
            <option value="Phase 1/2">Phase 1/2</option>
            <option value="Phase 2">Phase 2</option>
            <option value="Phase 2/3">Phase 2/3</option>
            <option value="Phase 3">Phase 3</option>
          </select>
        </div>

        {/* Workspaces List */}
        <div className="bg-white rounded-lg border overflow-hidden">
          <div className="px-6 py-4 border-b bg-gray-50">
            <h2 className="font-semibold text-gray-900">Study Workspaces</h2>
          </div>

          {loading ? (
            <div className="p-12 text-center">
              <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto" />
              <p className="mt-2 text-gray-500">Loading workspaces...</p>
            </div>
          ) : filteredWorkspaces.length === 0 ? (
            <div className="p-12 text-center">
              <FileText className="w-12 h-12 text-gray-300 mx-auto mb-3" />
              {workspaces.length === 0 ? (
                <>
                  <p className="text-gray-500">No study workspaces yet</p>
                  <p className="text-sm text-gray-400 mt-1">
                    Create your first workspace to get started
                  </p>
                  <button
                    onClick={() => setShowCreateModal(true)}
                    className="mt-4 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                  >
                    Create First Study
                  </button>
                </>
              ) : (
                <p className="text-gray-500">No workspaces match your filters</p>
              )}
            </div>
          ) : (
            <div className="divide-y">
              {filteredWorkspaces.map((ws) => (
                <div
                  key={ws.id}
                  onClick={() => router.push(`/workbench/${ws.id}`)}
                  className="px-6 py-4 flex items-center justify-between cursor-pointer hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <div className="p-2 bg-indigo-100 rounded-lg">
                      <FileText className="w-5 h-5 text-indigo-600" />
                    </div>
                    <div>
                      <h3 className="font-medium text-gray-900">{ws.name}</h3>
                      <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
                        {ws.phase && (
                          <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded text-xs font-medium">
                            {ws.phase}
                          </span>
                        )}
                        {ws.therapeutic_area && (
                          <span className="capitalize">{ws.therapeutic_area}</span>
                        )}
                        {ws.indication && (
                          <>
                            <span>•</span>
                            <span>{ws.indication}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <div className="text-sm text-gray-500">
                        {new Date(ws.created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <ChevronRight className="w-5 h-5 text-gray-400" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4">
            <div className="p-6 border-b flex items-center justify-between">
              <h2 className="text-xl font-semibold text-gray-900">Create Study Workspace</h2>
              <button
                onClick={resetCreateForm}
                className="p-1 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            <form onSubmit={handleCreateWorkspace} className="p-6 space-y-6">
              {/* File Upload */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Protocol Document
                </label>
                <div
                  className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors ${
                    dragActive
                      ? 'border-indigo-500 bg-indigo-50'
                      : 'border-gray-300 hover:border-gray-400'
                  }`}
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                >
                  {file ? (
                    <div className="flex items-center justify-center gap-3">
                      <FileText className="w-8 h-8 text-green-500" />
                      <div className="text-left">
                        <p className="font-medium text-gray-900">{file.name}</p>
                        <p className="text-sm text-gray-500">
                          {(file.size / 1024).toFixed(1)} KB
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => setFile(null)}
                        className="p-1 hover:bg-gray-100 rounded"
                      >
                        <X className="w-4 h-4 text-gray-400" />
                      </button>
                    </div>
                  ) : (
                    <div>
                      <Upload className="w-10 h-10 text-gray-400 mx-auto mb-2" />
                      <p className="text-sm text-gray-600">
                        Drag and drop your protocol, or{' '}
                        <label className="text-indigo-600 hover:text-indigo-500 cursor-pointer font-medium">
                          browse
                          <input
                            type="file"
                            className="hidden"
                            onChange={handleFileChange}
                            accept=".pdf,.docx,.doc,.txt"
                          />
                        </label>
                      </p>
                      <p className="text-xs text-gray-400 mt-1">PDF, DOCX, or TXT up to 50MB</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Study Metadata */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Phase</label>
                  <select
                    value={phase}
                    onChange={(e) => setPhase(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
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
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Therapeutic Area
                  </label>
                  <select
                    value={therapeuticArea}
                    onChange={(e) => setTherapeuticArea(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  >
                    <option value="oncology">Oncology</option>
                    <option value="cardiology">Cardiology</option>
                    <option value="neurology">Neurology</option>
                    <option value="immunology">Immunology</option>
                    <option value="infectious_disease">Infectious Disease</option>
                    <option value="rare_disease">Rare Disease</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Indication (Optional)
                </label>
                <input
                  type="text"
                  value={indication}
                  onChange={(e) => setIndication(e.target.value)}
                  placeholder="e.g., NSCLC, Breast Cancer, CRC"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>

              {error && (
                <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                  <AlertCircle className="w-4 h-4" />
                  {error}
                </div>
              )}

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={resetCreateForm}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!file || creating}
                  className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                  {creating ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    <>
                      <Plus className="w-4 h-4" />
                      Create Workspace
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

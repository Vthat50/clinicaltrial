'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import {
  ChevronLeft,
  ChevronRight,
  FileText,
  Play,
  RefreshCw,
  Check,
  Edit3,
  Save,
  X,
  Download,
  AlertCircle,
  CheckCircle,
  Clock,
  Loader2,
  BookOpen,
  List,
  FileCheck,
  Eye,
  Settings,
  Info,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Types
interface Metadata {
  study_id: string
  study_title: string
  phase: string
  therapeutic_area: string
  indication: string
  disease_setting: string
  performance_status_scale: string
  response_criteria: string
  geographic_countries: string[]
  endpoints: any[]
  populations: any[]
  treatment_arms: any[]
  stratification_factors: string[]
  sample_size: number | null
  prohibition_rules: string[]
  extraction_method: string
}

interface Section {
  id: string
  name: string
  display_name?: string
  status: string
  has_content: boolean
  version: number
}

interface SectionContent {
  id: string
  name: string
  display_name: string
  status: string
  content: string
  protocol_excerpts_used: string[]
  metadata_used: string[]
  version: number
}

// Status color helper
const getStatusConfig = (status: string) => {
  switch (status) {
    case 'approved':
      return { bg: 'bg-green-100', text: 'text-green-800', icon: CheckCircle, label: 'Approved' }
    case 'edited':
      return { bg: 'bg-blue-100', text: 'text-blue-800', icon: Edit3, label: 'Edited' }
    case 'draft':
      return { bg: 'bg-yellow-100', text: 'text-yellow-800', icon: FileText, label: 'Draft' }
    case 'generating':
      return { bg: 'bg-purple-100', text: 'text-purple-800', icon: Loader2, label: 'Generating' }
    default:
      return { bg: 'bg-gray-100', text: 'text-gray-600', icon: Clock, label: 'Not Started' }
  }
}

export default function WorkspacePage() {
  const params = useParams()
  const router = useRouter()
  const workspaceId = params.id as string

  // Data state
  const [metadata, setMetadata] = useState<Metadata | null>(null)
  const [outline, setOutline] = useState<Section[]>([])
  const [selectedSection, setSelectedSection] = useState<string | null>(null)
  const [sectionContent, setSectionContent] = useState<SectionContent | null>(null)

  // UI state
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const [generatingSection, setGeneratingSection] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [saving, setSaving] = useState(false)

  // Panel visibility
  const [showLeftPanel, setShowLeftPanel] = useState(true)
  const [showRightPanel, setShowRightPanel] = useState(true)

  // Fetch metadata on load
  useEffect(() => {
    fetchMetadata()
  }, [workspaceId])

  const fetchMetadata = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_URL}/workbench/${workspaceId}/metadata`)
      if (!res.ok) throw new Error('Failed to load workspace')
      const data = await res.json()
      setMetadata(data)
      await fetchOutline()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const fetchOutline = async () => {
    try {
      const res = await fetch(`${API_URL}/workbench/${workspaceId}/outline`)
      if (res.ok) {
        const data = await res.json()
        setOutline(data.sections || [])
      }
    } catch (e) {
      console.error('Failed to fetch outline:', e)
    }
  }

  const handleSelectSection = async (sectionId: string) => {
    setSelectedSection(sectionId)
    setEditing(false)

    const section = outline.find((s) => s.id === sectionId)
    if (section?.has_content) {
      try {
        const res = await fetch(`${API_URL}/workbench/${workspaceId}/section/${sectionId}`)
        if (res.ok) {
          const data = await res.json()
          setSectionContent(data)
          setEditContent(data.content)
        }
      } catch (e) {
        console.error('Failed to fetch section:', e)
      }
    } else {
      setSectionContent(null)
      setEditContent('')
    }
  }

  const handleGenerate = async (regenerate: boolean = false) => {
    if (!selectedSection) return

    setGenerating(true)
    setGeneratingSection(selectedSection)
    setError(null)

    try {
      const url = `${API_URL}/workbench/${workspaceId}/generate/${selectedSection}${regenerate ? '?regenerate=true' : ''}`
      const res = await fetch(url, { method: 'POST' })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Generation failed')
      }

      const data = await res.json()
      setSectionContent(data)
      setEditContent(data.content)
      await fetchOutline()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setGenerating(false)
      setGeneratingSection(null)
    }
  }

  const handleSave = async () => {
    if (!selectedSection) return

    setSaving(true)
    try {
      const res = await fetch(`${API_URL}/workbench/${workspaceId}/section/${selectedSection}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: editContent }),
      })

      if (res.ok) {
        const data = await res.json()
        setSectionContent(data)
        setEditing(false)
        await fetchOutline()
      }
    } catch (e) {
      console.error('Failed to save:', e)
    } finally {
      setSaving(false)
    }
  }

  const handleApprove = async () => {
    if (!selectedSection) return

    try {
      await fetch(`${API_URL}/workbench/${workspaceId}/section/${selectedSection}/approve`, {
        method: 'POST',
      })
      await fetchOutline()
      if (sectionContent) {
        setSectionContent({ ...sectionContent, status: 'approved' })
      }
    } catch (e) {
      console.error('Failed to approve:', e)
    }
  }

  const handleExport = async () => {
    try {
      const res = await fetch(`${API_URL}/workbench/${workspaceId}/export`)
      if (res.ok) {
        const data = await res.json()
        const blob = new Blob([data.content], { type: 'text/markdown' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `SAP_${metadata?.study_id || workspaceId}.md`
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch (e) {
      console.error('Export failed:', e)
    }
  }

  // Calculate progress
  const totalSections = outline.length
  const completedSections = outline.filter((s) => s.has_content).length
  const approvedSections = outline.filter((s) => s.status === 'approved').length
  const progress = totalSections > 0 ? Math.round((completedSections / totalSections) * 100) : 0

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto" />
          <p className="mt-2 text-gray-600">Loading workspace...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Top Bar */}
      <div className="bg-white border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.push('/workbench')}
            className="text-gray-500 hover:text-gray-700 flex items-center gap-1"
          >
            <ChevronLeft className="w-4 h-4" />
            Back
          </button>
          <div className="border-l pl-4">
            <h1 className="font-semibold text-gray-900 truncate max-w-md">
              {metadata?.study_title || 'Study Workspace'}
            </h1>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              {metadata?.study_id && <span>{metadata.study_id}</span>}
              {metadata?.phase && (
                <>
                  <span>•</span>
                  <span>{metadata.phase}</span>
                </>
              )}
              {metadata?.extraction_method === 'kg_55_category' && (
                <>
                  <span>•</span>
                  <span className="text-green-600">KG Extraction</span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Progress */}
          <div className="flex items-center gap-2 text-sm">
            <div className="w-32 h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-indigo-600 transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="text-gray-600">
              {completedSections}/{totalSections}
            </span>
          </div>

          {/* Export */}
          <button
            onClick={handleExport}
            className="flex items-center gap-2 px-3 py-1.5 text-sm border border-gray-300 rounded-md hover:bg-gray-50"
          >
            <Download className="w-4 h-4" />
            Export
          </button>
        </div>
      </div>

      {/* Main Content - 3 Pane Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Section Navigation */}
        <div
          className={`bg-white border-r transition-all duration-300 ${
            showLeftPanel ? 'w-72' : 'w-0'
          } overflow-hidden`}
        >
          <div className="h-full flex flex-col">
            {/* Panel Header */}
            <div className="p-3 border-b flex items-center justify-between">
              <h2 className="font-medium text-gray-900 flex items-center gap-2">
                <List className="w-4 h-4" />
                SAP Sections
              </h2>
              <span className="text-xs text-gray-500">
                {approvedSections} approved
              </span>
            </div>

            {/* Section List */}
            <div className="flex-1 overflow-y-auto p-2">
              {outline.map((section) => {
                const config = getStatusConfig(section.status)
                const isSelected = selectedSection === section.id
                const isGenerating = generatingSection === section.id

                return (
                  <button
                    key={section.id}
                    onClick={() => handleSelectSection(section.id)}
                    className={`w-full text-left p-3 rounded-lg mb-1 transition-colors ${
                      isSelected
                        ? 'bg-indigo-50 border border-indigo-200'
                        : 'hover:bg-gray-50 border border-transparent'
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <div
                        className={`w-2 h-2 rounded-full mt-1.5 ${
                          section.status === 'approved'
                            ? 'bg-green-500'
                            : section.has_content
                            ? 'bg-yellow-500'
                            : 'bg-gray-300'
                        }`}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-sm text-gray-900 truncate">
                          {section.display_name || section.name}
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <span
                            className={`text-xs px-1.5 py-0.5 rounded ${config.bg} ${config.text}`}
                          >
                            {isGenerating ? (
                              <span className="flex items-center gap-1">
                                <Loader2 className="w-3 h-3 animate-spin" />
                                Generating
                              </span>
                            ) : (
                              config.label
                            )}
                          </span>
                          {section.version > 1 && (
                            <span className="text-xs text-gray-400">v{section.version}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>

            {/* Generate All Button */}
            <div className="p-3 border-t">
              <button
                disabled={generating}
                className="w-full py-2 text-sm font-medium text-indigo-600 border border-indigo-200 rounded-md hover:bg-indigo-50 disabled:opacity-50"
              >
                Generate All Remaining
              </button>
            </div>
          </div>
        </div>

        {/* Toggle Left Panel */}
        <button
          onClick={() => setShowLeftPanel(!showLeftPanel)}
          className="w-6 bg-gray-100 hover:bg-gray-200 flex items-center justify-center border-r"
        >
          {showLeftPanel ? (
            <ChevronLeft className="w-4 h-4 text-gray-500" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-500" />
          )}
        </button>

        {/* Center Panel - Section Editor */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {error && (
            <div className="m-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700">
              <AlertCircle className="w-4 h-4" />
              {error}
              <button onClick={() => setError(null)} className="ml-auto">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {selectedSection ? (
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* Section Header */}
              <div className="p-4 border-b bg-white flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-gray-900">
                    {sectionContent?.display_name ||
                      outline.find((s) => s.id === selectedSection)?.name ||
                      selectedSection}
                  </h2>
                  {sectionContent && (
                    <div className="flex items-center gap-2 mt-1">
                      <span
                        className={`text-xs px-2 py-0.5 rounded ${
                          getStatusConfig(sectionContent.status).bg
                        } ${getStatusConfig(sectionContent.status).text}`}
                      >
                        {getStatusConfig(sectionContent.status).label}
                      </span>
                      <span className="text-xs text-gray-500">Version {sectionContent.version}</span>
                    </div>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  {!sectionContent ? (
                    <button
                      onClick={() => handleGenerate(false)}
                      disabled={generating}
                      className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
                    >
                      {generating ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Generating...
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4" />
                          Generate Section
                        </>
                      )}
                    </button>
                  ) : editing ? (
                    <>
                      <button
                        onClick={handleSave}
                        disabled={saving}
                        className="flex items-center gap-2 px-3 py-1.5 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50"
                      >
                        {saving ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Save className="w-4 h-4" />
                        )}
                        Save
                      </button>
                      <button
                        onClick={() => {
                          setEditing(false)
                          setEditContent(sectionContent.content)
                        }}
                        className="px-3 py-1.5 border border-gray-300 rounded-md hover:bg-gray-50"
                      >
                        Cancel
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        onClick={() => handleGenerate(true)}
                        disabled={generating}
                        className="flex items-center gap-2 px-3 py-1.5 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
                      >
                        <RefreshCw className={`w-4 h-4 ${generating ? 'animate-spin' : ''}`} />
                        Regenerate
                      </button>
                      <button
                        onClick={() => setEditing(true)}
                        className="flex items-center gap-2 px-3 py-1.5 border border-gray-300 rounded-md hover:bg-gray-50"
                      >
                        <Edit3 className="w-4 h-4" />
                        Edit
                      </button>
                      {sectionContent.status !== 'approved' && (
                        <button
                          onClick={handleApprove}
                          className="flex items-center gap-2 px-3 py-1.5 bg-green-600 text-white rounded-md hover:bg-green-700"
                        >
                          <Check className="w-4 h-4" />
                          Approve
                        </button>
                      )}
                    </>
                  )}
                </div>
              </div>

              {/* Section Content */}
              <div className="flex-1 overflow-y-auto">
                {sectionContent ? (
                  editing ? (
                    <textarea
                      value={editContent}
                      onChange={(e) => setEditContent(e.target.value)}
                      className="w-full h-full p-4 font-mono text-sm resize-none focus:outline-none"
                      placeholder="Enter section content..."
                    />
                  ) : (
                    <div className="p-6 prose prose-sm max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {sectionContent.content}
                      </ReactMarkdown>
                    </div>
                  )
                ) : (
                  <div className="flex-1 flex items-center justify-center text-gray-500">
                    <div className="text-center">
                      <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                      <p>No content yet</p>
                      <p className="text-sm">Click "Generate Section" to create content</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-500">
              <div className="text-center">
                <BookOpen className="w-12 h-12 mx-auto mb-3 text-gray-300" />
                <p>Select a section from the left panel</p>
                <p className="text-sm">or generate all sections at once</p>
              </div>
            </div>
          )}
        </div>

        {/* Toggle Right Panel */}
        <button
          onClick={() => setShowRightPanel(!showRightPanel)}
          className="w-6 bg-gray-100 hover:bg-gray-200 flex items-center justify-center border-l"
        >
          {showRightPanel ? (
            <ChevronRight className="w-4 h-4 text-gray-500" />
          ) : (
            <ChevronLeft className="w-4 h-4 text-gray-500" />
          )}
        </button>

        {/* Right Panel - Provenance & Protocol */}
        <div
          className={`bg-white border-l transition-all duration-300 ${
            showRightPanel ? 'w-80' : 'w-0'
          } overflow-hidden`}
        >
          <div className="h-full flex flex-col">
            {/* Panel Tabs */}
            <div className="border-b">
              <div className="flex">
                <button className="flex-1 px-4 py-3 text-sm font-medium border-b-2 border-indigo-500 text-indigo-600">
                  Provenance
                </button>
                <button className="flex-1 px-4 py-3 text-sm font-medium text-gray-500 hover:text-gray-700">
                  Protocol
                </button>
              </div>
            </div>

            {/* Panel Content */}
            <div className="flex-1 overflow-y-auto p-4">
              {sectionContent ? (
                <div className="space-y-4">
                  {/* Protocol Excerpts */}
                  {sectionContent.protocol_excerpts_used.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-900 mb-2 flex items-center gap-2">
                        <FileText className="w-4 h-4" />
                        Protocol Excerpts Used
                      </h3>
                      <div className="space-y-2">
                        {sectionContent.protocol_excerpts_used.map((excerpt, i) => (
                          <div
                            key={i}
                            className="p-3 bg-blue-50 border border-blue-100 rounded-lg text-sm text-blue-800"
                          >
                            <p className="italic">"{excerpt}"</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Metadata Used */}
                  {sectionContent.metadata_used.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-900 mb-2 flex items-center gap-2">
                        <Info className="w-4 h-4" />
                        Extracted Facts Used
                      </h3>
                      <div className="space-y-1">
                        {sectionContent.metadata_used.map((fact, i) => (
                          <div
                            key={i}
                            className="p-2 bg-gray-50 rounded text-sm text-gray-700"
                          >
                            {fact}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* No provenance */}
                  {sectionContent.protocol_excerpts_used.length === 0 &&
                    sectionContent.metadata_used.length === 0 && (
                      <div className="text-center text-gray-500 py-8">
                        <Eye className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                        <p className="text-sm">No provenance data available</p>
                      </div>
                    )}
                </div>
              ) : metadata ? (
                <div className="space-y-4">
                  {/* Study Info */}
                  <div>
                    <h3 className="text-sm font-medium text-gray-900 mb-2">Study Information</h3>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-500">Phase</span>
                        <span className="font-medium">{metadata.phase || '-'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Setting</span>
                        <span className="font-medium capitalize">{metadata.disease_setting || '-'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Sample Size</span>
                        <span className="font-medium">{metadata.sample_size || '-'}</span>
                      </div>
                    </div>
                  </div>

                  {/* Prohibition Rules */}
                  {metadata.prohibition_rules.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-900 mb-2">Protocol Rules</h3>
                      <div className="space-y-1">
                        {metadata.prohibition_rules.map((rule, i) => (
                          <div
                            key={i}
                            className="p-2 bg-amber-50 border border-amber-100 rounded text-xs text-amber-800"
                          >
                            {rule}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Endpoints */}
                  {metadata.endpoints.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium text-gray-900 mb-2">Endpoints</h3>
                      <div className="space-y-2">
                        {metadata.endpoints.slice(0, 5).map((ep, i) => (
                          <div key={i} className="p-2 bg-gray-50 rounded text-sm">
                            <span
                              className={`text-xs px-1.5 py-0.5 rounded mr-2 ${
                                ep.type === 'primary'
                                  ? 'bg-indigo-100 text-indigo-700'
                                  : 'bg-gray-200 text-gray-600'
                              }`}
                            >
                              {ep.type}
                            </span>
                            <span className="font-medium">{ep.name}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center text-gray-500 py-8">
                  <p className="text-sm">Select a section to view provenance</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

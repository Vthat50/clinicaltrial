'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Play,
  RefreshCw,
  Save,
  Edit3,
  Check,
  X,
  FileText,
  BookOpen,
  ExternalLink,
  Loader2,
  AlertCircle,
  CheckCircle,
  Eye,
  Code,
  ChevronRight,
  Download,
  BarChart3,
  ChevronDown,
  ChevronUp,
  Database,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useWorkspaceStore, SAPSection, selectFlatOutline } from '../stores/workspaceStore'
import SAPOutlineTree from './SAPOutlineTree'
import ProtocolOverlay from './ProtocolOverlay'
import SectionSourcesPanel from './SectionSourcesPanel'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface KBToolUsed {
  tool_name: string
  source_file: string
  source_key: string
  description: string
}

interface SectionContent {
  id: string
  name: string
  display_name: string
  status: string
  content: string
  protocol_excerpts_used: string[]
  metadata_used: string[]
  kb_tools_used: KBToolUsed[]
  version: number
  generated_at: string
}

interface SAPAuthoringSuiteProps {
  workspaceId: string
  protocolUrl?: string
}

export default function SAPAuthoringSuite({ workspaceId, protocolUrl }: SAPAuthoringSuiteProps) {
  const {
    outline,
    setOutline,
    selectedSectionId,
    selectSection,
    updateSectionStatus,
    ui,
    toggleOutline,
    toggleProtocolOverlay,
    closeProtocolOverlay,
    scroll,
    setSapEditorScroll,
    teleportToProtocol,
  } = useWorkspaceStore()

  const flatOutline = useWorkspaceStore(selectFlatOutline)

  // Local state
  const [sectionContent, setSectionContent] = useState<SectionContent | null>(null)
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'preview' | 'edit' | 'split'>('preview')

  // v100.3: Accuracy comparison state
  const [comparisonResult, setComparisonResult] = useState<any>(null)
  const [checkingAccuracy, setCheckingAccuracy] = useState(false)
  const [showComparison, setShowComparison] = useState(false)

  // v101: Section sources panel
  const [showSources, setShowSources] = useState(false)

  const editorRef = useRef<HTMLTextAreaElement>(null)
  const previewRef = useRef<HTMLDivElement>(null)

  // Fetch outline on mount
  useEffect(() => {
    fetchOutline()
  }, [workspaceId])

  // Fetch section content when selection changes
  useEffect(() => {
    if (selectedSectionId) {
      fetchSectionContent(selectedSectionId)
    } else {
      setSectionContent(null)
    }
  }, [selectedSectionId])

  // Restore scroll position
  useEffect(() => {
    if (previewRef.current) {
      previewRef.current.scrollTop = scroll.sapEditor
    }
  }, [])

  const fetchOutline = async () => {
    try {
      const res = await fetch(`${API_URL}/workbench/${workspaceId}/outline`)
      if (res.ok) {
        const data = await res.json()
        // Transform to tree structure if needed
        setOutline(transformToTree(data.sections || []))
      }
    } catch (e) {
      console.error('Failed to fetch outline:', e)
    }
  }

  const fetchSectionContent = async (sectionId: string) => {
    const section = flatOutline.find((s) => s.id === sectionId)
    if (!section?.has_content) {
      setSectionContent(null)
      return
    }

    // Only show loading spinner if we're switching to a different section
    // Don't show loading if we already have content for this section
    const isNewSection = sectionContent?.id !== sectionId
    if (isNewSection) {
      setLoading(true)
    }

    try {
      const res = await fetch(`${API_URL}/workbench/${workspaceId}/section/${sectionId}`)
      if (res.ok) {
        const data = await res.json()
        setSectionContent(data)
        setEditContent(data.content)
      }
    } catch (e) {
      console.error('Failed to fetch section:', e)
    } finally {
      if (isNewSection) {
        setLoading(false)
      }
    }
  }

  const handleGenerate = async (regenerate = false) => {
    if (!selectedSectionId) return
    await generateSectionById(selectedSectionId, regenerate)
  }

  // Generate a specific section by ID (used by "Generate All Remaining")
  const generateSectionById = async (sectionId: string, regenerate = false): Promise<void> => {
    setGenerating(true)
    setError(null)
    updateSectionStatus(sectionId, 'generating')

    try {
      const url = `${API_URL}/workbench/${workspaceId}/generate/${sectionId}${regenerate ? '?regenerate=true' : ''}`
      const res = await fetch(url, { method: 'POST' })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Generation failed')
      }

      const data = await res.json()
      // Only update UI if this is the currently selected section
      if (sectionId === selectedSectionId) {
        setSectionContent(data)
        setEditContent(data.content)
      }
      // Update status AND has_content locally so clicking the section works immediately
      updateSectionStatus(sectionId, 'draft', true)
      await fetchOutline()
    } catch (e: any) {
      setError(e.message)
      updateSectionStatus(sectionId, 'not_started')
      throw e  // Re-throw so caller knows it failed
    } finally {
      setGenerating(false)
    }
  }

  const handleSave = async () => {
    if (!selectedSectionId) return

    setSaving(true)
    try {
      const res = await fetch(`${API_URL}/workbench/${workspaceId}/section/${selectedSectionId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: editContent }),
      })

      if (res.ok) {
        const data = await res.json()
        setSectionContent(data)
        setEditing(false)
        setViewMode('preview')
        updateSectionStatus(selectedSectionId, 'edited')
        await fetchOutline()
      }
    } catch (e) {
      console.error('Failed to save:', e)
    } finally {
      setSaving(false)
    }
  }

  const handleApprove = async () => {
    if (!selectedSectionId) return

    try {
      await fetch(`${API_URL}/workbench/${workspaceId}/section/${selectedSectionId}/approve`, {
        method: 'POST',
      })
      updateSectionStatus(selectedSectionId, 'approved')
      if (sectionContent) {
        setSectionContent({ ...sectionContent, status: 'approved' })
      }
      await fetchOutline()
    } catch (e) {
      console.error('Failed to approve:', e)
    }
  }

  // v100.3: Check accuracy against reference SAP
  const handleCheckAccuracy = async () => {
    if (!selectedSectionId) return

    setCheckingAccuracy(true)
    setComparisonResult(null)

    try {
      const res = await fetch(`${API_URL}/workbench/${workspaceId}/compare/${selectedSectionId}`, {
        method: 'POST',
      })

      if (res.ok) {
        const data = await res.json()
        setComparisonResult(data)
        setShowComparison(true)
      } else {
        const err = await res.json()
        setError(err.detail || 'Failed to check accuracy')
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setCheckingAccuracy(false)
    }
  }

  const handleScroll = () => {
    if (previewRef.current) {
      setSapEditorScroll(previewRef.current.scrollTop)
    }
  }

  const handleViewInProtocol = (sourceQuote: string) => {
    teleportToProtocol(sourceQuote, null)
  }

  const selectedSection = flatOutline.find((s) => s.id === selectedSectionId)

  return (
    <div className="flex-1 flex h-full overflow-hidden">
      {/* Collapsible Outline */}
      <SAPOutlineTree
        isCollapsed={ui.outlineCollapsed}
        onToggleCollapse={toggleOutline}
        onGenerateSection={async (id) => {
          selectSection(id)
          await generateSectionById(id, false)
        }}
      />

      {/* Main Editor Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Error Banner */}
        {error && (
          <div className="px-4 py-2 bg-red-50 border-b border-red-200 flex items-center gap-2 text-red-700 shrink-0">
            <AlertCircle className="w-4 h-4" />
            <span className="text-sm">{error}</span>
            <button onClick={() => setError(null)} className="ml-auto">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {selectedSectionId ? (
          <>
            {/* Section Header */}
            <div className="px-4 py-3 bg-white border-b flex items-center justify-between shrink-0">
              <div className="flex items-center gap-3">
                <div>
                  <h2 className="font-semibold text-gray-900">
                    {selectedSection?.display_name || selectedSection?.name || selectedSectionId}
                  </h2>
                  {sectionContent && (
                    <div className="flex items-center gap-2 mt-1">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full ${
                          sectionContent.status === 'approved'
                            ? 'bg-green-100 text-green-700'
                            : sectionContent.status === 'edited'
                            ? 'bg-blue-100 text-blue-700'
                            : sectionContent.status === 'draft'
                            ? 'bg-yellow-100 text-yellow-700'
                            : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {sectionContent.status}
                      </span>
                      <span className="text-xs text-gray-500">v{sectionContent.version}</span>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2">
                {/* Quick Reference Toggle */}
                <button
                  onClick={toggleProtocolOverlay}
                  className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors flex items-center gap-2 ${
                    ui.protocolOverlayOpen
                      ? 'bg-blue-600 text-white'
                      : 'border border-gray-300 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <BookOpen className="w-4 h-4" />
                  Protocol Reference
                </button>

                {/* Section Sources Toggle */}
                <button
                  onClick={() => setShowSources(!showSources)}
                  className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors flex items-center gap-2 ${
                    showSources
                      ? 'bg-blue-600 text-white'
                      : 'border border-gray-300 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <Database className="w-4 h-4" />
                  Sources
                  {sectionContent?.kb_tools_used && sectionContent.kb_tools_used.length > 0 && (
                    <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                      showSources ? 'bg-blue-500 text-white' : 'bg-blue-100 text-blue-700'
                    }`}>
                      {sectionContent.kb_tools_used.length}
                    </span>
                  )}
                </button>

                {/* View Mode Toggle */}
                <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden">
                  <button
                    onClick={() => setViewMode('preview')}
                    className={`px-3 py-1.5 text-sm ${
                      viewMode === 'preview'
                        ? 'bg-gray-100 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <Eye className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setViewMode('edit')}
                    className={`px-3 py-1.5 text-sm ${
                      viewMode === 'edit'
                        ? 'bg-gray-100 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <Code className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setViewMode('split')}
                    className={`px-3 py-1.5 text-sm ${
                      viewMode === 'split'
                        ? 'bg-gray-100 text-gray-900'
                        : 'text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    Split
                  </button>
                </div>

                {/* Action Buttons */}
                {!sectionContent ? (
                  <button
                    onClick={() => handleGenerate(false)}
                    disabled={generating}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
                  >
                    {generating ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Generating...
                      </>
                    ) : (
                      <>
                        <Play className="w-4 h-4" />
                        Generate
                      </>
                    )}
                  </button>
                ) : viewMode === 'edit' || viewMode === 'split' ? (
                  <>
                    <button
                      onClick={handleSave}
                      disabled={saving}
                      className="flex items-center gap-2 px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
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
                        setViewMode('preview')
                        setEditContent(sectionContent.content)
                      }}
                      className="px-3 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      Cancel
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      onClick={() => handleGenerate(true)}
                      disabled={generating}
                      className="flex items-center gap-2 px-3 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 transition-colors"
                    >
                      <RefreshCw className={`w-4 h-4 ${generating ? 'animate-spin' : ''}`} />
                      Regenerate
                    </button>
                    {/* Check Accuracy Button */}
                    <button
                      onClick={handleCheckAccuracy}
                      disabled={checkingAccuracy}
                      className="flex items-center gap-2 px-3 py-1.5 border border-indigo-300 text-indigo-600 rounded-lg hover:bg-indigo-50 disabled:opacity-50 transition-colors"
                    >
                      {checkingAccuracy ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Checking...
                        </>
                      ) : (
                        <>
                          <BarChart3 className="w-4 h-4" />
                          Check Accuracy
                        </>
                      )}
                    </button>
                    {sectionContent.status !== 'approved' && (
                      <button
                        onClick={handleApprove}
                        className="flex items-center gap-2 px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                      >
                        <CheckCircle className="w-4 h-4" />
                        Approve
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 flex overflow-hidden">
              {/* Editor Panel */}
              {(viewMode === 'edit' || viewMode === 'split') && (
                <div className={`${viewMode === 'split' ? 'w-1/2' : 'flex-1'} flex flex-col border-r`}>
                  <div className="px-3 py-2 bg-gray-50 border-b text-xs text-gray-500 font-medium">
                    MARKDOWN EDITOR
                  </div>
                  <textarea
                    ref={editorRef}
                    value={editContent}
                    onChange={(e) => setEditContent(e.target.value)}
                    className="flex-1 w-full p-4 font-mono text-sm resize-none focus:outline-none"
                    placeholder="Enter section content in Markdown..."
                  />
                </div>
              )}

              {/* Preview Panel */}
              {(viewMode === 'preview' || viewMode === 'split') && (
                <div className={`${viewMode === 'split' ? 'w-1/2' : 'flex-1'} flex flex-col`}>
                  {viewMode === 'split' && (
                    <div className="px-3 py-2 bg-gray-50 border-b text-xs text-gray-500 font-medium">
                      PREVIEW
                    </div>
                  )}
                  <div
                    ref={previewRef}
                    className="flex-1 overflow-y-auto"
                    onScroll={handleScroll}
                  >
                    {loading ? (
                      <div className="flex items-center justify-center h-full">
                        <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
                      </div>
                    ) : sectionContent ? (
                      <div className="p-6">
                        <div className="prose prose-sm max-w-none">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {viewMode === 'split' ? editContent : sectionContent.content}
                          </ReactMarkdown>
                        </div>

                        {/* Provenance Section */}
                        {(sectionContent.protocol_excerpts_used.length > 0 ||
                          sectionContent.metadata_used.length > 0) && (
                          <div className="mt-8 pt-6 border-t">
                            <h4 className="text-sm font-medium text-gray-900 mb-4">Sources & Provenance</h4>

                            {sectionContent.protocol_excerpts_used.length > 0 && (
                              <div className="mb-4">
                                <h5 className="text-xs font-medium text-gray-500 uppercase mb-2">
                                  Protocol Excerpts
                                </h5>
                                <div className="space-y-2">
                                  {sectionContent.protocol_excerpts_used.map((excerpt, i) => (
                                    <div
                                      key={i}
                                      className="p-3 bg-blue-50 border border-blue-100 rounded-lg text-sm text-blue-800 flex items-start gap-2"
                                    >
                                      <p className="flex-1 italic">"{excerpt}"</p>
                                      <button
                                        onClick={() => handleViewInProtocol(excerpt)}
                                        className="p-1 hover:bg-blue-100 rounded"
                                        title="View in Protocol"
                                      >
                                        <ExternalLink className="w-4 h-4" />
                                      </button>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}

                            {sectionContent.metadata_used.length > 0 && (
                              <div>
                                <h5 className="text-xs font-medium text-gray-500 uppercase mb-2">
                                  Extracted Facts Used
                                </h5>
                                <div className="flex flex-wrap gap-2">
                                  {sectionContent.metadata_used.map((fact, i) => (
                                    <span
                                      key={i}
                                      className="px-2 py-1 bg-gray-100 rounded text-sm text-gray-700"
                                    >
                                      {fact}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center h-full text-gray-500 p-8">
                        <FileText className="w-12 h-12 text-gray-300 mb-4" />
                        <p className="text-lg font-medium text-gray-700 mb-2">No Content Yet</p>
                        <p className="text-sm text-center text-gray-500 mb-6">
                          Click "Generate" to create content for this section using extracted protocol facts.
                        </p>
                        <button
                          onClick={() => handleGenerate(false)}
                          disabled={generating}
                          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
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
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Section Sources Panel */}
              <SectionSourcesPanel
                section={sectionContent ? {
                  ...sectionContent,
                  id: sectionContent.id,
                  name: sectionContent.name,
                  display_name: sectionContent.display_name,
                  order: 0,
                  status: sectionContent.status as any,
                  has_content: !!sectionContent.content,
                  content: sectionContent.content,
                  version: sectionContent.version,
                  needs_update: false,
                  impacted_by_change: false,
                  protocol_excerpts_used: sectionContent.protocol_excerpts_used || [],
                  metadata_used: sectionContent.metadata_used || [],
                  kb_tools_used: sectionContent.kb_tools_used || [],
                  generated_at: sectionContent.generated_at,
                } : null}
                isOpen={showSources}
                onClose={() => setShowSources(false)}
              />
            </div>
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-gray-500 p-8">
            <FileText className="w-16 h-16 text-gray-300 mb-4" />
            <p className="text-lg font-medium text-gray-700 mb-2">Select a Section</p>
            <p className="text-sm text-center text-gray-500 max-w-md">
              Choose a section from the outline to view, edit, or generate content.
              The SAP will be built section by section using facts extracted from your protocol.
            </p>
          </div>
        )}
      </div>

      {/* Protocol Overlay */}
      <ProtocolOverlay
        isOpen={ui.protocolOverlayOpen}
        onClose={closeProtocolOverlay}
        protocolUrl={protocolUrl}
      />

      {/* Accuracy Comparison Panel */}
      {showComparison && comparisonResult && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t shadow-lg z-40 max-h-[50vh] overflow-y-auto">
          <div className="p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <BarChart3 className="w-5 h-5 text-indigo-600" />
                <h3 className="font-semibold text-gray-900">Accuracy Report</h3>
                {comparisonResult.comparison?.accuracy_percentage !== undefined && (
                  <span className={`px-2 py-1 text-sm font-medium rounded-full ${
                    comparisonResult.comparison.accuracy_percentage >= 80
                      ? 'bg-green-100 text-green-700'
                      : comparisonResult.comparison.accuracy_percentage >= 60
                      ? 'bg-yellow-100 text-yellow-700'
                      : 'bg-red-100 text-red-700'
                  }`}>
                    {comparisonResult.comparison.accuracy_percentage}% Match
                  </span>
                )}
              </div>
              <button
                onClick={() => setShowComparison(false)}
                className="p-1 hover:bg-gray-100 rounded"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            {/* Show matched reference section */}
            {comparisonResult.reference_section_id && (
              <div className="mb-3 text-sm text-gray-600 bg-gray-50 px-3 py-2 rounded-lg">
                Compared against: <span className="font-medium text-gray-800">
                  {comparisonResult.reference_section_id}
                  {comparisonResult.reference_section_title && comparisonResult.reference_section_title !== comparisonResult.reference_section_id &&
                    ` - ${comparisonResult.reference_section_title}`}
                </span>
                {comparisonResult.matched_via === 'semantic' && (
                  <span className="ml-2 text-xs text-indigo-600">(auto-matched)</span>
                )}
              </div>
            )}

            {!comparisonResult.has_reference ? (
              <div className="text-gray-500 text-sm">
                No reference SAP uploaded. Upload a reference SAP to enable accuracy checking.
              </div>
            ) : !comparisonResult.section_found ? (
              <div className="text-yellow-600 text-sm">
                {comparisonResult.message}
              </div>
            ) : comparisonResult.comparison ? (
              <div className="space-y-4">
                {/* Summary */}
                {comparisonResult.comparison.summary && (
                  <div className="text-sm text-gray-700 bg-gray-50 p-3 rounded-lg">
                    {comparisonResult.comparison.summary}
                  </div>
                )}

                {/* Missing Content */}
                {comparisonResult.comparison.missing_content?.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-red-700 mb-2 flex items-center gap-2">
                      <AlertCircle className="w-4 h-4" />
                      Missing Content ({comparisonResult.comparison.missing_content.length})
                    </h4>
                    <div className="space-y-2">
                      {comparisonResult.comparison.missing_content.map((item: any, i: number) => (
                        <div key={i} className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm">
                          <div className="font-medium text-red-800">{item.element}</div>
                          {item.original_text && (
                            <div className="text-red-600 mt-1 text-xs italic">
                              Original: "{item.original_text}"
                            </div>
                          )}
                          {item.suggestion && (
                            <div className="text-gray-700 mt-1 text-xs">
                              Suggestion: {item.suggestion}
                            </div>
                          )}
                          {item.importance && (
                            <span className={`inline-block mt-1 px-2 py-0.5 text-xs rounded ${
                              item.importance === 'critical' ? 'bg-red-200 text-red-800' :
                              item.importance === 'important' ? 'bg-yellow-200 text-yellow-800' :
                              'bg-gray-200 text-gray-800'
                            }`}>
                              {item.importance}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Incorrect Content */}
                {comparisonResult.comparison.incorrect_content?.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-orange-700 mb-2">
                      Incorrect Content ({comparisonResult.comparison.incorrect_content.length})
                    </h4>
                    <div className="space-y-2">
                      {comparisonResult.comparison.incorrect_content.map((item: any, i: number) => (
                        <div key={i} className="bg-orange-50 border border-orange-200 rounded-lg p-3 text-sm">
                          <div className="font-medium text-orange-800">{item.element}</div>
                          {item.original && (
                            <div className="text-green-600 mt-1 text-xs">
                              Should be: "{item.original}"
                            </div>
                          )}
                          {item.generated && (
                            <div className="text-red-600 mt-1 text-xs">
                              Generated: "{item.generated}"
                            </div>
                          )}
                          {item.suggestion && (
                            <div className="text-gray-700 mt-1 text-xs">
                              Fix: {item.suggestion}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Correct Content */}
                {comparisonResult.comparison.correct_content?.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-green-700 mb-2 flex items-center gap-2">
                      <CheckCircle className="w-4 h-4" />
                      Correct ({comparisonResult.comparison.correct_content.length})
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {comparisonResult.comparison.correct_content.map((item: string, i: number) => (
                        <span key={i} className="bg-green-50 border border-green-200 text-green-700 px-2 py-1 rounded text-xs">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Suggestions */}
                {comparisonResult.comparison.overall_suggestions?.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-blue-700 mb-2">
                      Suggestions
                    </h4>
                    <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
                      {comparisonResult.comparison.overall_suggestions.map((s: string, i: number) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  )
}

// Helper to transform flat sections array to nested tree
function transformToTree(sections: any[]): SAPSection[] {
  const sectionMap = new Map<string, SAPSection>()
  const roots: SAPSection[] = []

  // First pass: create all sections
  sections.forEach((s, index) => {
    const section: SAPSection = {
      id: s.id,
      name: s.name,
      display_name: s.display_name || s.name,
      parent_id: s.parent_id || null,
      order: s.order ?? index,
      level: s.level ?? 0,
      status: s.status || 'not_started',
      has_content: s.has_content || false,
      version: s.version || 1,
      children: [],
    }
    sectionMap.set(s.id, section)
  })

  // Second pass: build tree
  sectionMap.forEach((section) => {
    if (section.parent_id && sectionMap.has(section.parent_id)) {
      const parent = sectionMap.get(section.parent_id)!
      if (!parent.children) parent.children = []
      parent.children.push(section)
    } else {
      roots.push(section)
    }
  })

  // Sort by order
  const sortByOrder = (arr: SAPSection[]) => {
    arr.sort((a, b) => a.order - b.order)
    arr.forEach((s) => {
      if (s.children) sortByOrder(s.children)
    })
  }
  sortByOrder(roots)

  return roots
}

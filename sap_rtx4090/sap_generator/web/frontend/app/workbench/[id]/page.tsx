'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type Step = 'metadata' | 'outline' | 'generate' | 'provenance' | 'export'

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

export default function WorkspacePage() {
  const params = useParams()
  const router = useRouter()
  const workspaceId = params.id as string

  const [step, setStep] = useState<Step>('metadata')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Data states
  const [metadata, setMetadata] = useState<Metadata | null>(null)
  const [outline, setOutline] = useState<Section[]>([])
  const [selectedSection, setSelectedSection] = useState<string | null>(null)
  const [sectionContent, setSectionContent] = useState<SectionContent | null>(null)
  const [generating, setGenerating] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')

  // Fetch metadata on load
  useEffect(() => {
    fetchMetadata()
  }, [workspaceId])

  const fetchMetadata = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_URL}/workbench/${workspaceId}/metadata`)
      if (!res.ok) throw new Error('Failed to load metadata')
      const data = await res.json()
      setMetadata(data)
      // Also fetch outline
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

  const generateSection = async (sectionId: string) => {
    setGenerating(true)
    setError(null)
    try {
      const res = await fetch(`${API_URL}/workbench/${workspaceId}/generate/${sectionId}`, {
        method: 'POST'
      })
      if (!res.ok) throw new Error('Failed to generate section')
      const data = await res.json()
      setSectionContent(data)
      setEditContent(data.content)
      await fetchOutline()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setGenerating(false)
    }
  }

  const fetchSection = async (sectionId: string) => {
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
  }

  const saveSection = async () => {
    if (!selectedSection) return
    try {
      const res = await fetch(`${API_URL}/workbench/${workspaceId}/section/${selectedSection}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: editContent })
      })
      if (res.ok) {
        const data = await res.json()
        setSectionContent(data)
        setEditing(false)
        await fetchOutline()
      }
    } catch (e) {
      console.error('Failed to save section:', e)
    }
  }

  const approveSection = async (sectionId: string) => {
    try {
      await fetch(`${API_URL}/workbench/${workspaceId}/section/${sectionId}/approve`, {
        method: 'POST'
      })
      await fetchOutline()
    } catch (e) {
      console.error('Failed to approve section:', e)
    }
  }

  const exportSAP = async () => {
    try {
      const res = await fetch(`${API_URL}/workbench/${workspaceId}/export`)
      if (res.ok) {
        const data = await res.json()
        // Download as file
        const blob = new Blob([data.content], { type: 'text/markdown' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `SAP_${workspaceId}.md`
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch (e) {
      console.error('Export failed:', e)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'approved': return 'bg-green-100 text-green-800'
      case 'edited': return 'bg-blue-100 text-blue-800'
      case 'draft': return 'bg-yellow-100 text-yellow-800'
      case 'generating': return 'bg-purple-100 text-purple-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-500">Loading workspace...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <button onClick={() => router.push('/workbench')} className="text-gray-500 hover:text-gray-700 mb-2">
            &larr; Back to Workbench
          </button>
          <h1 className="text-2xl font-bold text-gray-900">
            {metadata?.study_title || 'Study Workspace'}
          </h1>
          {metadata?.study_id && (
            <p className="text-gray-500">{metadata.study_id}</p>
          )}
        </div>
        <button
          onClick={exportSAP}
          className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700"
        >
          Export SAP
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md">
          {error}
        </div>
      )}

      {/* Step Navigation */}
      <div className="bg-white rounded-lg shadow-sm border">
        <div className="flex border-b">
          {[
            { id: 'metadata', label: 'Protocol Summary', icon: '1' },
            { id: 'outline', label: 'SAP Outline', icon: '2' },
            { id: 'generate', label: 'Generate Sections', icon: '3' },
            { id: 'provenance', label: 'Traceability', icon: '4' },
            { id: 'export', label: 'Export', icon: '5' },
          ].map((s) => (
            <button
              key={s.id}
              onClick={() => setStep(s.id as Step)}
              className={`flex-1 py-4 px-4 text-center border-b-2 transition-colors ${
                step === s.id
                  ? 'border-indigo-500 text-indigo-600 bg-indigo-50'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50'
              }`}
            >
              <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-gray-200 text-xs font-medium mr-2">
                {s.icon}
              </span>
              {s.label}
            </button>
          ))}
        </div>

        {/* Step Content */}
        <div className="p-6">
          {/* Step 1: Metadata / Protocol Understanding */}
          {step === 'metadata' && metadata && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Protocol Understanding</h2>
                <span className={`px-3 py-1 rounded-full text-sm ${
                  metadata.extraction_method === 'kg_55_category'
                    ? 'bg-green-100 text-green-800'
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  {metadata.extraction_method === 'kg_55_category' ? '55-Category KG Extraction' : 'Basic Extraction'}
                </span>
              </div>

              {/* Prohibition Rules Alert */}
              {metadata.prohibition_rules.length > 0 && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                  <h3 className="font-medium text-amber-800 mb-2">Protocol-Specific Rules</h3>
                  <ul className="text-sm text-amber-700 space-y-1">
                    {metadata.prohibition_rules.map((rule, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-amber-500">!</span>
                        {rule}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Key Metadata Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-sm text-gray-500">Phase</div>
                  <div className="font-medium">{metadata.phase || '-'}</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-sm text-gray-500">Disease Setting</div>
                  <div className="font-medium capitalize">{metadata.disease_setting || '-'}</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-sm text-gray-500">Performance Status</div>
                  <div className="font-medium">{metadata.performance_status_scale || '-'}</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="text-sm text-gray-500">Sample Size</div>
                  <div className="font-medium">{metadata.sample_size || '-'}</div>
                </div>
              </div>

              {/* Countries */}
              {metadata.geographic_countries.length > 0 && (
                <div>
                  <h3 className="font-medium text-gray-900 mb-2">Geographic Scope</h3>
                  <div className="flex flex-wrap gap-2">
                    {metadata.geographic_countries.map((country, i) => (
                      <span key={i} className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                        {country}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Endpoints */}
              {metadata.endpoints.length > 0 && (
                <div>
                  <h3 className="font-medium text-gray-900 mb-2">Endpoints</h3>
                  <div className="space-y-2">
                    {metadata.endpoints.map((ep, i) => (
                      <div key={i} className="bg-gray-50 rounded-lg p-3">
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                            ep.type === 'primary' ? 'bg-indigo-100 text-indigo-800' : 'bg-gray-200 text-gray-700'
                          }`}>
                            {ep.type}
                          </span>
                          <span className="font-medium">{ep.name}</span>
                        </div>
                        {ep.definition && (
                          <p className="text-sm text-gray-600 mt-1">{ep.definition}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Treatment Arms */}
              {metadata.treatment_arms.length > 0 && (
                <div>
                  <h3 className="font-medium text-gray-900 mb-2">Treatment Arms</h3>
                  <div className="grid grid-cols-2 gap-3">
                    {metadata.treatment_arms.map((arm, i) => (
                      <div key={i} className="bg-gray-50 rounded-lg p-3">
                        <div className="font-medium">{arm.name}</div>
                        {arm.description && (
                          <p className="text-sm text-gray-600">{arm.description}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Stratification */}
              {metadata.stratification_factors.length > 0 && (
                <div>
                  <h3 className="font-medium text-gray-900 mb-2">Stratification Factors</h3>
                  <div className="flex flex-wrap gap-2">
                    {metadata.stratification_factors.map((factor, i) => (
                      <span key={i} className="px-3 py-1 bg-purple-100 text-purple-800 rounded-full text-sm">
                        {factor}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Step 2: SAP Outline */}
          {step === 'outline' && (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold">SAP Sections</h2>
              <p className="text-gray-600">Click on a section to generate or view its content.</p>

              <div className="space-y-2">
                {outline.map((section) => (
                  <div
                    key={section.id}
                    onClick={() => {
                      setSelectedSection(section.id)
                      if (section.has_content) {
                        fetchSection(section.id)
                      } else {
                        setSectionContent(null)
                      }
                      setStep('generate')
                    }}
                    className="flex items-center justify-between p-4 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-3 h-3 rounded-full ${
                        section.status === 'approved' ? 'bg-green-500' :
                        section.status === 'draft' || section.status === 'edited' ? 'bg-yellow-500' :
                        'bg-gray-300'
                      }`} />
                      <span className="font-medium">{section.name}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-1 rounded text-xs ${getStatusColor(section.status)}`}>
                        {section.status}
                      </span>
                      {section.version > 1 && (
                        <span className="text-xs text-gray-500">v{section.version}</span>
                      )}
                      <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Step 3: Generate/Edit Section */}
          {step === 'generate' && (
            <div className="space-y-4">
              {/* Section Selector */}
              <div className="flex items-center gap-4">
                <select
                  value={selectedSection || ''}
                  onChange={(e) => {
                    setSelectedSection(e.target.value)
                    const section = outline.find(s => s.id === e.target.value)
                    if (section?.has_content) {
                      fetchSection(e.target.value)
                    } else {
                      setSectionContent(null)
                    }
                  }}
                  className="flex-1 border border-gray-300 rounded-md px-3 py-2"
                >
                  <option value="">Select a section...</option>
                  {outline.map((section) => (
                    <option key={section.id} value={section.id}>
                      {section.name} ({section.status})
                    </option>
                  ))}
                </select>

                {selectedSection && (
                  <button
                    onClick={() => generateSection(selectedSection)}
                    disabled={generating}
                    className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700 disabled:bg-gray-400"
                  >
                    {generating ? 'Generating...' : sectionContent ? 'Regenerate' : 'Generate'}
                  </button>
                )}
              </div>

              {/* Section Content */}
              {sectionContent && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-lg font-medium">{sectionContent.display_name}</h3>
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-1 rounded text-xs ${getStatusColor(sectionContent.status)}`}>
                        {sectionContent.status}
                      </span>
                      {!editing && (
                        <>
                          <button
                            onClick={() => setEditing(true)}
                            className="text-indigo-600 hover:text-indigo-800 text-sm"
                          >
                            Edit
                          </button>
                          {sectionContent.status !== 'approved' && (
                            <button
                              onClick={() => approveSection(sectionContent.id)}
                              className="bg-green-600 text-white px-3 py-1 rounded text-sm hover:bg-green-700"
                            >
                              Approve
                            </button>
                          )}
                        </>
                      )}
                    </div>
                  </div>

                  {/* Protocol Excerpts Used */}
                  {sectionContent.protocol_excerpts_used.length > 0 && (
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                      <h4 className="text-sm font-medium text-blue-800 mb-2">Protocol Excerpts Used</h4>
                      <div className="text-sm text-blue-700 space-y-2">
                        {sectionContent.protocol_excerpts_used.map((excerpt, i) => (
                          <p key={i} className="italic">"{excerpt}"</p>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Content Editor */}
                  {editing ? (
                    <div className="space-y-2">
                      <textarea
                        value={editContent}
                        onChange={(e) => setEditContent(e.target.value)}
                        className="w-full h-96 border border-gray-300 rounded-lg p-4 font-mono text-sm"
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={saveSection}
                          className="bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700"
                        >
                          Save Changes
                        </button>
                        <button
                          onClick={() => {
                            setEditing(false)
                            setEditContent(sectionContent.content)
                          }}
                          className="text-gray-600 hover:text-gray-800 px-4 py-2"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="bg-white border rounded-lg p-4 prose max-w-none">
                      <pre className="whitespace-pre-wrap font-sans text-sm">{sectionContent.content}</pre>
                    </div>
                  )}
                </div>
              )}

              {!selectedSection && (
                <div className="text-center py-12 text-gray-500">
                  Select a section from the dropdown or go to SAP Outline to choose a section.
                </div>
              )}
            </div>
          )}

          {/* Step 4: Provenance/Traceability */}
          {step === 'provenance' && (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold">Traceability Report</h2>
              <p className="text-gray-600">See where each section's content comes from.</p>

              <div className="space-y-4">
                {outline.filter(s => s.has_content).map((section) => (
                  <div key={section.id} className="border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="font-medium">{section.name}</h3>
                      <span className={`px-2 py-1 rounded text-xs ${getStatusColor(section.status)}`}>
                        {section.status}
                      </span>
                    </div>
                    <div className="text-sm text-gray-600">
                      <p>Version: {section.version}</p>
                      <p>Sources: Protocol extraction, Knowledge base standards</p>
                    </div>
                  </div>
                ))}
              </div>

              {outline.filter(s => s.has_content).length === 0 && (
                <div className="text-center py-12 text-gray-500">
                  No sections generated yet. Generate sections first to see traceability.
                </div>
              )}
            </div>
          )}

          {/* Step 5: Export */}
          {step === 'export' && (
            <div className="space-y-6">
              <h2 className="text-xl font-semibold">Export SAP</h2>

              {/* Progress Summary */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-medium mb-3">Completion Status</h3>
                <div className="space-y-2">
                  {outline.map((section) => (
                    <div key={section.id} className="flex items-center gap-2">
                      <div className={`w-4 h-4 rounded-full flex items-center justify-center ${
                        section.status === 'approved' ? 'bg-green-500' :
                        section.has_content ? 'bg-yellow-500' : 'bg-gray-300'
                      }`}>
                        {section.status === 'approved' && (
                          <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                          </svg>
                        )}
                      </div>
                      <span className={section.status === 'approved' ? 'text-green-700' : 'text-gray-600'}>
                        {section.name}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Export Buttons */}
              <div className="flex gap-4">
                <button
                  onClick={exportSAP}
                  className="flex-1 bg-indigo-600 text-white py-3 rounded-md hover:bg-indigo-700"
                >
                  Download as Markdown
                </button>
                <button
                  disabled
                  className="flex-1 bg-gray-200 text-gray-500 py-3 rounded-md cursor-not-allowed"
                >
                  Download as Word (Coming Soon)
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { Loader2, AlertCircle, Download, X, Upload, CheckCircle } from 'lucide-react'
import { useWorkspaceStore, ExtractionFact, selectFlaggedFacts } from '../stores/workspaceStore'
import ContextRail from '../components/ContextRail'
import ProtocolAuditSuite from '../components/ProtocolAuditSuite'
import SAPAuthoringSuite from '../components/SAPAuthoringSuite'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Metadata from the workspace
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
  // Schedule of Assessments (SOA)
  visit_schedule?: Array<{ visit: string; timing: string; window: string }>
  tumor_assessment_frequency?: string
  pro_collection_visits?: string[]
  follow_up_schedule?: string
}

// Warning can be a string or an object
type Warning = string | {
  term_found?: string
  expected_category?: string
  recommendation?: string
  message?: string
}

// Provenance info for facts
interface SourceInfo {
  source_quote?: string
  source_section?: string
}

// Extraction data structure
interface ExtractionData {
  workspace_id: string
  extraction_method: string
  extraction_timestamp: string
  study_info: {
    nct_id: string
    protocol_number: string
    sponsor: string
    title: string
    phase: string
    source_quote?: string
    source_section?: string
  }
  design: {
    type: string
    blinding: string
    randomization_ratio: string
    control_type: string
    source_quote?: string
    source_section?: string
  }
  study_types: {
    is_cart: boolean
    is_hematologic: boolean
    is_immunotherapy: boolean
  }
  endpoints: {
    primary: Array<{ name: string; definition: string; type: string; source_quote?: string; source_section?: string }>
    secondary: Array<{ name: string; definition: string; type: string; source_quote?: string; source_section?: string }>
    exploratory?: Array<{ name: string; definition: string; type: string; source_quote?: string; source_section?: string }>
  }
  populations: Array<{
    name: string
    definition: string
    is_primary_efficacy: boolean
    is_primary_safety: boolean
    source_quote?: string
    source_section?: string
  }>
  sample_size: {
    total_n: number | null
    power: string | null
    alpha: string | null
    effect_size: string | null
    enrollment_by_arm?: Record<string, number>
    source_quote?: string
    source_section?: string
  }
  subgroups: Array<{ factor: string; categories: string[]; is_stratification_factor: boolean; source_quote?: string; source_section?: string }>
  censoring_rules: Array<{ endpoint: string; scenario: string; source_quote?: string; source_section?: string }>
  prohibition_rules: string[]
  cart_specific: {
    crs_scale: string
    icans_scale: string
    bridging_therapy: boolean
  } | null
  // Schedule of Assessments (SOA)
  schedule_of_assessments?: {
    visits: Array<{ visit: string; timing: string; window: string }>
    tumor_assessment_frequency: string
    pro_collection_visits: string[]
    follow_up_schedule: string
  }
  warnings: Warning[]
  completeness: {
    total_endpoints: number
    total_populations: number
    total_subgroups: number
    confidence: string
    all_captured: boolean
  }
  raw_field_count: number
}

export default function WorkspacePage() {
  const params = useParams()
  const workspaceId = params.id as string

  // Global workspace state
  const {
    viewMode,
    setWorkspaceId,
    setFacts,
    reset,
  } = useWorkspaceStore()

  const flaggedFacts = useWorkspaceStore(selectFlaggedFacts)

  // Local state
  const [metadata, setMetadata] = useState<Metadata | null>(null)
  const [extractionData, setExtractionData] = useState<ExtractionData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // v100.3: Reference SAP state
  const [referenceSapStatus, setReferenceSapStatus] = useState<{
    has_reference: boolean
    filename?: string
    sections_count?: number
  } | null>(null)
  const [uploadingReference, setUploadingReference] = useState(false)

  // Check reference SAP status
  const checkReferenceSapStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/workbench/${workspaceId}/reference-sap/status`)
      if (res.ok) {
        const data = await res.json()
        setReferenceSapStatus(data)
      }
    } catch (e) {
      console.error('Failed to check reference SAP status:', e)
    }
  }

  // Upload reference SAP
  const handleUploadReferenceSap = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploadingReference(true)
    try {
      const formData = new FormData()
      formData.append('file', file)

      const res = await fetch(`${API_URL}/workbench/${workspaceId}/reference-sap`, {
        method: 'POST',
        body: formData,
      })

      if (res.ok) {
        const data = await res.json()
        setReferenceSapStatus({
          has_reference: true,
          filename: data.filename,
          sections_count: data.sections_parsed,
        })
        alert(`Reference SAP uploaded! Parsed ${data.sections_parsed} sections.`)
      } else {
        const err = await res.json()
        alert(`Failed to upload: ${err.detail || 'Unknown error'}`)
      }
    } catch (e: any) {
      alert(`Upload failed: ${e.message}`)
    } finally {
      setUploadingReference(false)
      // Reset file input
      e.target.value = ''
    }
  }

  // Initialize workspace
  useEffect(() => {
    setWorkspaceId(workspaceId)
    loadWorkspaceData()
    checkReferenceSapStatus()

    return () => {
      // Don't reset on unmount to preserve state across navigation
    }
  }, [workspaceId])

  const loadWorkspaceData = async () => {
    setLoading(true)
    setError(null)

    try {
      // Fetch metadata and extraction data in parallel
      const [metadataRes, extractionRes] = await Promise.all([
        fetch(`${API_URL}/workbench/${workspaceId}/metadata`),
        fetch(`${API_URL}/workbench/${workspaceId}/extraction`),
      ])

      if (!metadataRes.ok) {
        throw new Error('Failed to load workspace')
      }

      const metadataData = await metadataRes.json()
      setMetadata(metadataData)

      if (extractionRes.ok) {
        const extractionDataResult = await extractionRes.json()
        setExtractionData(extractionDataResult)

        // Transform extraction data to facts for the store
        const facts = transformExtractionToFacts(extractionDataResult)
        setFacts(facts)
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
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

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto" />
          <p className="mt-3 text-gray-600">Loading workspace...</p>
          <p className="text-sm text-gray-400 mt-1">Preparing protocol and extraction data</p>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center max-w-md">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Failed to Load Workspace</h2>
          <p className="text-gray-600 mb-6">{error}</p>
          <button
            onClick={loadWorkspaceData}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen flex bg-gray-50">
      {/* Context Rail - Persistent Left Navigation */}
      <ContextRail
        workspaceId={workspaceId}
        flaggedCount={flaggedFacts.filter((f) => f.status === 'flagged').length}
        warningCount={flaggedFacts.filter((f) => f.status === 'warning').length}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Global Top Bar */}
        <div className="bg-white border-b px-4 py-2 flex items-center justify-between shrink-0 z-10">
          <div className="flex items-center gap-4">
            <div>
              <h1 className="font-semibold text-gray-900 truncate max-w-lg">
                {metadata?.study_title || 'Study Workspace'}
              </h1>
              <div className="flex items-center gap-2 text-sm text-gray-500">
                {metadata?.study_id && <span>{metadata.study_id}</span>}
                {metadata?.phase && (
                  <>
                    <span className="text-gray-300">|</span>
                    <span>{metadata.phase}</span>
                  </>
                )}
                {metadata?.extraction_method === 'kg_55_category' && (
                  <>
                    <span className="text-gray-300">|</span>
                    <span className="text-green-600 font-medium">55-Category KG</span>
                  </>
                )}
                {extractionData && (
                  <>
                    <span className="text-gray-300">|</span>
                    <span className="text-indigo-600">{extractionData.raw_field_count} fields</span>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* View Mode Indicator */}
            <div className="flex items-center gap-1 px-3 py-1.5 bg-gray-100 rounded-lg">
              <span className="text-xs text-gray-500 uppercase tracking-wide">
                {viewMode === 'protocol-audit' ? 'Protocol Audit' : 'SAP Authoring'}
              </span>
            </div>

            {/* Upload Reference SAP (Optional) */}
            <div className="relative">
              <input
                type="file"
                accept=".pdf,.txt,.md"
                onChange={handleUploadReferenceSap}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                disabled={uploadingReference}
              />
              <button
                className={`flex items-center gap-2 px-3 py-1.5 text-sm border rounded-lg transition-colors ${
                  referenceSapStatus?.has_reference
                    ? 'border-green-300 bg-green-50 text-green-700'
                    : 'border-gray-300 hover:bg-gray-50'
                }`}
                disabled={uploadingReference}
              >
                {uploadingReference ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Uploading...
                  </>
                ) : referenceSapStatus?.has_reference ? (
                  <>
                    <CheckCircle className="w-4 h-4" />
                    Reference SAP ({referenceSapStatus.sections_count} sections)
                  </>
                ) : (
                  <>
                    <Upload className="w-4 h-4" />
                    Upload Reference SAP
                  </>
                )}
              </button>
            </div>

            {/* Export */}
            <button
              onClick={handleExport}
              className="flex items-center gap-2 px-3 py-1.5 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <Download className="w-4 h-4" />
              Export SAP
            </button>
          </div>
        </div>

        {/* Task Suite Content */}
        <div className="flex-1 overflow-hidden">
          {viewMode === 'protocol-audit' ? (
            <ProtocolAuditSuite
              workspaceId={workspaceId}
              protocolTitle={metadata?.study_title}
              studyId={metadata?.study_id}
            />
          ) : (
            <SAPAuthoringSuite workspaceId={workspaceId} />
          )}
        </div>
      </div>
    </div>
  )
}

// Helper to transform extraction data into facts for the store
function transformExtractionToFacts(data: ExtractionData): ExtractionFact[] {
  const facts: ExtractionFact[] = []
  let factId = 0

  const generateId = () => `fact_${++factId}`

  // Study info - share source info across study_info fields
  if (data.study_info) {
    const si = data.study_info
    const studySource = { source_quote: si.source_quote, source_section: si.source_section }
    if (si.nct_id) facts.push({ id: generateId(), category: 'study_info', name: 'NCT ID', value: si.nct_id, status: 'verified', ...studySource })
    if (si.protocol_number) facts.push({ id: generateId(), category: 'study_info', name: 'Protocol Number', value: si.protocol_number, status: 'verified', ...studySource })
    if (si.sponsor) facts.push({ id: generateId(), category: 'study_info', name: 'Sponsor', value: si.sponsor, status: 'verified', ...studySource })
    if (si.phase) facts.push({ id: generateId(), category: 'study_info', name: 'Phase', value: si.phase, status: 'verified', ...studySource })
  }

  // Design - share source info across design fields
  if (data.design) {
    const d = data.design
    const designSource = { source_quote: d.source_quote, source_section: d.source_section }
    if (d.type) facts.push({ id: generateId(), category: 'design', name: 'Design Type', value: d.type, status: 'verified', ...designSource })
    if (d.blinding) facts.push({ id: generateId(), category: 'design', name: 'Blinding', value: d.blinding, status: 'verified', ...designSource })
    if (d.randomization_ratio) facts.push({ id: generateId(), category: 'design', name: 'Randomization Ratio', value: d.randomization_ratio, status: 'verified', ...designSource })
    if (d.control_type) facts.push({ id: generateId(), category: 'design', name: 'Control Type', value: d.control_type, status: 'verified', ...designSource })
  }

  // Primary endpoints - each endpoint has its own provenance
  data.endpoints.primary.forEach((ep) => {
    facts.push({
      id: generateId(),
      category: 'endpoints',
      subcategory: 'primary',
      name: ep.name,
      value: ep.type,
      definition: ep.definition,
      status: 'verified',
      source_quote: ep.source_quote,
      source_section: ep.source_section,
    })
  })

  // Secondary endpoints
  data.endpoints.secondary.forEach((ep) => {
    facts.push({
      id: generateId(),
      category: 'endpoints',
      subcategory: 'secondary',
      name: ep.name,
      value: ep.type,
      definition: ep.definition,
      status: 'verified',
      source_quote: ep.source_quote,
      source_section: ep.source_section,
    })
  })

  // Populations - each population has its own provenance
  data.populations.forEach((pop) => {
    facts.push({
      id: generateId(),
      category: 'populations',
      name: pop.name,
      value: pop.is_primary_efficacy ? 'Primary Efficacy' : pop.is_primary_safety ? 'Primary Safety' : 'Other',
      definition: pop.definition,
      status: 'verified',
      source_quote: pop.source_quote,
      source_section: pop.source_section,
    })
  })

  // Sample size
  if (data.sample_size) {
    const ss = data.sample_size
    const sampleSource = { source_quote: ss.source_quote, source_section: ss.source_section }
    if (ss.total_n) facts.push({ id: generateId(), category: 'sample_size', name: 'Total N', value: ss.total_n, status: 'verified', ...sampleSource })
    if (ss.power) facts.push({ id: generateId(), category: 'sample_size', name: 'Power', value: ss.power, status: 'verified', ...sampleSource })
    if (ss.alpha) facts.push({ id: generateId(), category: 'sample_size', name: 'Alpha', value: ss.alpha, status: 'verified', ...sampleSource })
    if (ss.effect_size) facts.push({ id: generateId(), category: 'sample_size', name: 'Effect Size', value: ss.effect_size, status: 'verified', ...sampleSource })
  }

  // Subgroups - each subgroup has its own provenance
  data.subgroups.forEach((sg) => {
    facts.push({
      id: generateId(),
      category: 'subgroups',
      name: sg.factor,
      value: sg.categories.join(', '),
      status: sg.is_stratification_factor ? 'verified' : 'unverified',
      source_quote: sg.source_quote,
      source_section: sg.source_section,
    })
  })

  // Censoring rules - each rule has its own provenance
  data.censoring_rules.forEach((cr) => {
    facts.push({
      id: generateId(),
      category: 'censoring',
      name: cr.endpoint,
      value: cr.scenario,
      status: 'verified',
      source_quote: cr.source_quote,
      source_section: cr.source_section,
    })
  })

  // Prohibition rules (string array, no provenance)
  data.prohibition_rules.forEach((rule) => {
    facts.push({
      id: generateId(),
      category: 'prohibitions',
      name: 'Prohibition Rule',
      value: rule,
      status: 'warning',
      warning_message: 'Protocol restriction - ensure compliance in SAP',
    })
  })

  // CAR-T specific
  if (data.cart_specific) {
    const cart = data.cart_specific
    if (cart.crs_scale) facts.push({ id: generateId(), category: 'cart_specific', name: 'CRS Scale', value: cart.crs_scale, status: 'verified' })
    if (cart.icans_scale) facts.push({ id: generateId(), category: 'cart_specific', name: 'ICANS Scale', value: cart.icans_scale, status: 'verified' })
    facts.push({ id: generateId(), category: 'cart_specific', name: 'Bridging Therapy', value: cart.bridging_therapy, status: 'verified' })
  }

  // Warnings become flagged facts
  data.warnings.forEach((warning) => {
    const warningText = typeof warning === 'string'
      ? warning
      : warning.message || warning.recommendation || JSON.stringify(warning)

    facts.push({
      id: generateId(),
      category: 'study_info',
      name: 'Extraction Warning',
      value: warningText,
      status: 'flagged',
      warning_message: warningText,
    })
  })

  // Deduplicate facts by category+name+value combination
  const seen = new Set<string>()
  const dedupedFacts = facts.filter((fact) => {
    const key = `${fact.category}|${fact.name}|${fact.value}`
    if (seen.has(key)) {
      return false
    }
    seen.add(key)
    return true
  })

  return dedupedFacts
}

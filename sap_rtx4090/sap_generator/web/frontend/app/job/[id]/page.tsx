'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Helper function to download text as a file
function downloadTextFile(content: string, filename: string) {
  if (!content || content.length === 0) {
    alert('Error: No content to download!')
    return
  }

  // Open in new tab - user can Ctrl+S to save
  const newWindow = window.open('', '_blank')
  if (newWindow) {
    newWindow.document.write('<pre style="white-space: pre-wrap; word-wrap: break-word; font-family: monospace; padding: 20px;">' + content.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</pre>')
    newWindow.document.title = filename
    newWindow.document.close()
  } else {
    // If popup blocked, copy to clipboard
    navigator.clipboard.writeText(content).then(() => {
      alert('Content copied to clipboard! Paste into a text file and save as ' + filename)
    }).catch(() => {
      alert('Please enable popups or use the Copy button instead.')
    })
  }
}

interface JobResult {
  job_id: string
  status: string
  generated_sap?: string
  quality_score?: number
  endpoint_type?: string
  phase?: string
  therapeutic_area?: string
  processing_time?: number
  error_message?: string
  created_at?: string
  completed_at?: string
  filename?: string
  protocol_preview?: string
}

interface GroundTruthStudy {
  nct_id: string
  title: string
  sap_lines: number
  therapeutic_area: string
  quality?: 'high' | 'standard'
}

interface EvaluationResult {
  nct_id: string
  ground_truth_lines: number
  generated_lines: number
  section_coverage_pct: number
  keyword_overlap_pct: number
  has_primary_endpoint: boolean
  has_secondary_endpoint: boolean
  has_sample_size: boolean
  has_analysis_populations: boolean
  has_statistical_methods: boolean
  has_missing_data: boolean
  overall_score: number
  sections_matched: string[]
  sections_missing: string[]
  statistical_terms_found: string[]
  statistical_terms_missing: string[]
}

interface BatchEvaluationResult {
  total_comparisons: number
  aggregate: {
    avg_section_coverage_pct: number
    avg_keyword_overlap_pct: number
    avg_overall_score: number
    primary_endpoint_pct: number
    statistical_methods_pct: number
  }
  best_match: {
    nct_id: string
    overall_score: number
    quality: string
  } | null
  worst_match: {
    nct_id: string
    overall_score: number
    quality: string
  } | null
  results: Array<{
    nct_id: string
    quality: string
    section_coverage_pct: number
    keyword_overlap_pct: number
    overall_score: number
  }>
}

interface SDTMVariable {
  name: string
  label: string
  type: string
  length: number | null
  core: string
  codelist: string | null
}

interface SAPTraceability {
  sap_section: string
  sap_text: string
  sdtm_element: string
  rationale: string
}

interface SDTMDomain {
  code: string
  name: string
  label: string
  class: string
  structure: string
  purpose: string
  variables: SDTMVariable[]
  traceability?: SAPTraceability[]
  study_specific_notes?: string[]
}

interface SAPSummary {
  primary_endpoint?: string
  primary_timepoint?: string
  secondary_endpoints?: string[]
  populations?: string[]
  treatment_arms?: string[]
  sample_size?: number
}

interface SDTMSpecResult {
  success: boolean
  message: string
  sdtm_version: string
  domains: SDTMDomain[]
  domain_count: number
  markdown: string
  sap_summary?: SAPSummary
  errors: string[]
}

// TLF Shell interfaces
interface TLFColumn {
  header: string
  width: number
  align: string
}

interface TLFShell {
  output_id: string
  title: string
  population: string
  footnotes: string[]
  columns: TLFColumn[]
  markdown: string
}

interface TLFShellResult {
  success: boolean
  message: string
  tables: TLFShell[]
  listings: TLFShell[]
  figures: TLFShell[]
  total_outputs: number
  markdown: string
  errors: string[]
}

// ADaM Spec interfaces
interface AdamVariable {
  name: string
  label: string
  type: string
  length: number
  derivation: string
  source: string
  codelist: string | null
}

interface AdamDataset {
  name: string
  label: string
  structure: string
  keys: string[]
  variables: AdamVariable[]
}

interface AdamSpecResult {
  success: boolean
  message: string
  datasets: AdamDataset[]
  total_variables: number
  markdown: string
  errors: string[]
}

// Define-XML interfaces
interface DefineXMLResult {
  success: boolean
  message: string
  xml_content: string
  dataset_count: number
  variable_count: number
  standard_type: string
  errors: string[]
}

export default function JobDetailPage() {
  const params = useParams()
  const router = useRouter()
  const jobId = params.id as string

  const [result, setResult] = useState<JobResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'sap' | 'sdtm' | 'tlf' | 'adam' | 'definexml' | 'protocol'>('sap')

  // SDTM Specs state
  const [sdtmSpec, setSdtmSpec] = useState<SDTMSpecResult | null>(null)
  const [sdtmLoading, setSdtmLoading] = useState(false)
  const [sdtmError, setSdtmError] = useState<string | null>(null)
  const [expandedDomain, setExpandedDomain] = useState<string | null>(null)

  // TLF Shells state
  const [tlfResult, setTlfResult] = useState<TLFShellResult | null>(null)
  const [tlfLoading, setTlfLoading] = useState(false)
  const [tlfError, setTlfError] = useState<string | null>(null)

  // ADaM Specs state
  const [adamResult, setAdamResult] = useState<AdamSpecResult | null>(null)
  const [adamLoading, setAdamLoading] = useState(false)
  const [adamError, setAdamError] = useState<string | null>(null)
  const [expandedDataset, setExpandedDataset] = useState<string | null>(null)

  // Define-XML state
  const [defineXmlResult, setDefineXmlResult] = useState<DefineXMLResult | null>(null)
  const [defineXmlLoading, setDefineXmlLoading] = useState(false)
  const [defineXmlError, setDefineXmlError] = useState<string | null>(null)
  const [defineXmlStandard, setDefineXmlStandard] = useState<'adam' | 'sdtm'>('adam')

  // Evaluation state
  const [groundTruthStudies, setGroundTruthStudies] = useState<GroundTruthStudy[]>([])
  const [selectedStudy, setSelectedStudy] = useState<string>('')
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null)
  const [evaluating, setEvaluating] = useState(false)
  const [evalError, setEvalError] = useState<string | null>(null)

  // Batch evaluation state
  const [batchEvaluation, setBatchEvaluation] = useState<BatchEvaluationResult | null>(null)
  const [batchEvaluating, setBatchEvaluating] = useState(false)
  const [batchError, setBatchError] = useState<string | null>(null)
  const [showBatchDetails, setShowBatchDetails] = useState(false)
  const [batchLimit, setBatchLimit] = useState<number>(30)

  // Fetch ground truth studies on mount
  useEffect(() => {
    async function fetchGroundTruth() {
      try {
        const res = await fetch(`${API_URL}/ground-truth`)
        if (res.ok) {
          const data = await res.json()
          setGroundTruthStudies(data.studies || [])
        }
      } catch (e) {
        console.error('Failed to fetch ground truth studies:', e)
      }
    }
    fetchGroundTruth()
  }, [])

  // Run evaluation
  const runEvaluation = async () => {
    if (!selectedStudy || !jobId) return

    setEvaluating(true)
    setEvalError(null)
    setEvaluation(null)

    try {
      const res = await fetch(`${API_URL}/evaluate/${jobId}?ground_truth_nct=${selectedStudy}`, {
        method: 'POST'
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Evaluation failed')
      }

      const data = await res.json()
      setEvaluation(data)
    } catch (e: any) {
      setEvalError(e.message)
    } finally {
      setEvaluating(false)
    }
  }

  // Run batch evaluation against all ground truth SAPs
  const runBatchEvaluation = async () => {
    if (!jobId) return

    setBatchEvaluating(true)
    setBatchError(null)
    setBatchEvaluation(null)

    try {
      const res = await fetch(`${API_URL}/evaluate-batch/${jobId}?limit=${batchLimit}`, {
        method: 'POST'
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Batch evaluation failed')
      }

      const data = await res.json()
      setBatchEvaluation(data)
    } catch (e: any) {
      setBatchError(e.message)
    } finally {
      setBatchEvaluating(false)
    }
  }

  // Generate SDTM specifications
  const generateSdtmSpecs = async () => {
    if (!jobId) return

    setSdtmLoading(true)
    setSdtmError(null)

    try {
      const res = await fetch(`${API_URL}/generate-sdtm/${jobId}`, {
        method: 'POST'
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'SDTM generation failed')
      }

      const data = await res.json()
      if (data.success) {
        setSdtmSpec(data)
      } else {
        throw new Error(data.message || 'SDTM generation failed')
      }
    } catch (e: any) {
      setSdtmError(e.message)
    } finally {
      setSdtmLoading(false)
    }
  }

  // Generate TLF shells
  const generateTlfShells = async () => {
    if (!jobId) return

    setTlfLoading(true)
    setTlfError(null)

    try {
      const res = await fetch(`${API_URL}/generate-tlf-shells/${jobId}`, {
        method: 'POST'
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'TLF generation failed')
      }

      const data = await res.json()
      if (data.success) {
        setTlfResult(data)
      } else {
        throw new Error(data.message || 'TLF generation failed')
      }
    } catch (e: any) {
      setTlfError(e.message)
    } finally {
      setTlfLoading(false)
    }
  }

  // Generate ADaM derivation specs
  const generateAdamSpecs = async () => {
    if (!jobId) return

    setAdamLoading(true)
    setAdamError(null)

    try {
      const res = await fetch(`${API_URL}/generate-adam-specs/${jobId}`, {
        method: 'POST'
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'ADaM spec generation failed')
      }

      const data = await res.json()
      if (data.success) {
        setAdamResult(data)
      } else {
        throw new Error(data.message || 'ADaM spec generation failed')
      }
    } catch (e: any) {
      setAdamError(e.message)
    } finally {
      setAdamLoading(false)
    }
  }

  // Generate Define-XML
  const generateDefineXml = async () => {
    if (!jobId) return

    setDefineXmlLoading(true)
    setDefineXmlError(null)

    try {
      const res = await fetch(`${API_URL}/generate-define-xml/${jobId}?standard=${defineXmlStandard}`, {
        method: 'POST'
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Define-XML generation failed')
      }

      const data = await res.json()
      if (data.success) {
        setDefineXmlResult(data)
      } else {
        throw new Error(data.message || 'Define-XML generation failed')
      }
    } catch (e: any) {
      setDefineXmlError(e.message)
    } finally {
      setDefineXmlLoading(false)
    }
  }

  // Poll for status updates
  useEffect(() => {
    let interval: NodeJS.Timeout

    async function fetchJob() {
      try {
        const res = await fetch(`${API_URL}/status/${jobId}`)
        if (!res.ok) throw new Error('Job not found')
        const data = await res.json()
        setResult(data)
        setLoading(false)

        // Stop polling when job is done
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(interval)
        }
      } catch (e: any) {
        setError(e.message)
        setLoading(false)
        clearInterval(interval)
      }
    }

    if (jobId) {
      fetchJob()
      // Poll every 3 seconds for status updates
      interval = setInterval(fetchJob, 3000)
    }

    return () => clearInterval(interval)
  }, [jobId])

  if (loading) {
    return (
      <div className="flex flex-col justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mb-4"></div>
        <p className="text-gray-600">Loading job details...</p>
      </div>
    )
  }

  if (error || !result) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="bg-red-50 border border-red-200 rounded-xl p-6">
          <h3 className="text-lg font-medium text-red-800">Error</h3>
          <p className="mt-2 text-red-700">{error || 'Job not found'}</p>
          <Link href="/" className="mt-4 inline-block text-indigo-600 hover:underline">
            ← Back to Home
          </Link>
        </div>
      </div>
    )
  }

  const isProcessing = result.status === 'queued' || result.status === 'processing'

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link href="/" className="text-sm text-gray-500 hover:text-indigo-600">
            ← Back to Home
          </Link>
          <h1 className="text-2xl font-bold text-gray-900 mt-2">
            {result.filename || `Job ${jobId.slice(0, 8)}`}
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Created: {result.created_at ? new Date(result.created_at).toLocaleString() : 'N/A'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`px-4 py-2 rounded-full text-sm font-medium ${
            result.status === 'completed' ? 'bg-green-100 text-green-800' :
            result.status === 'failed' ? 'bg-red-100 text-red-800' :
            result.status === 'processing' ? 'bg-blue-100 text-blue-800' :
            'bg-yellow-100 text-yellow-800'
          }`}>
            {isProcessing && (
              <span className="inline-block w-2 h-2 bg-current rounded-full mr-2 animate-pulse"></span>
            )}
            {result.status.charAt(0).toUpperCase() + result.status.slice(1)}
          </span>
        </div>
      </div>

      {/* Processing State */}
      {isProcessing && (
        <div className="bg-white rounded-xl shadow-sm border p-8">
          <div className="flex flex-col items-center text-center">
            <div className="relative">
              <div className="animate-spin rounded-full h-16 w-16 border-4 border-indigo-100 border-t-indigo-600"></div>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-xl">🤖</span>
              </div>
            </div>
            <h2 className="text-xl font-semibold text-gray-900 mt-6">
              {result.status === 'queued' ? 'Job Queued' : 'Generating SAP...'}
            </h2>
            <p className="text-gray-600 mt-2 max-w-md">
              {result.status === 'queued'
                ? 'Your job is in the queue. Processing will begin shortly.'
                : 'Analyzing protocol and generating Statistical Analysis Plan. This typically takes 60-90 seconds.'}
            </p>
            <div className="mt-6 w-full max-w-xs">
              <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                <div className="h-full bg-indigo-600 rounded-full animate-pulse" style={{width: result.status === 'queued' ? '20%' : '60%'}}></div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Error State */}
      {result.status === 'failed' && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6">
          <div className="flex items-start">
            <span className="text-2xl mr-3">❌</span>
            <div>
              <h3 className="text-lg font-medium text-red-800">Generation Failed</h3>
              <p className="mt-2 text-red-700">{result.error_message || 'An unknown error occurred'}</p>
              <button
                onClick={() => router.push('/')}
                className="mt-4 bg-red-600 text-white py-2 px-4 rounded-lg hover:bg-red-700 transition-colors"
              >
                Try Again
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Completed State */}
      {result.status === 'completed' && (
        <>
          {/* Evaluation Panel - At Top */}
          {groundTruthStudies.length > 0 && (
            <div className="bg-gradient-to-r from-purple-50 to-indigo-50 rounded-xl shadow-sm border border-purple-200 p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <span className="text-xl">🎯</span>
                  <h3 className="text-lg font-semibold text-gray-900">Evaluate Against Ground Truth</h3>
                </div>
                {evaluation && (
                  <div className={`px-4 py-2 rounded-full font-bold text-lg ${
                    evaluation.overall_score >= 70 ? 'bg-green-100 text-green-700' :
                    evaluation.overall_score >= 50 ? 'bg-yellow-100 text-yellow-700' :
                    'bg-red-100 text-red-700'
                  }`}>
                    Score: {evaluation.overall_score}/100
                  </div>
                )}
              </div>

              {/* Study Selector */}
              <div className="flex gap-3 mb-4">
                <select
                  value={selectedStudy}
                  onChange={(e) => setSelectedStudy(e.target.value)}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 text-sm"
                >
                  <option value="">Select from {groundTruthStudies.length} ground truth studies...</option>
                  <optgroup label="High Quality (Real SAP PDFs)">
                    {groundTruthStudies.filter(s => s.quality === 'high').map((study) => (
                      <option key={study.nct_id} value={study.nct_id}>
                        {study.nct_id} - {study.title} ({study.sap_lines} lines)
                      </option>
                    ))}
                  </optgroup>
                  <optgroup label="Standard (AACT Database)">
                    {groundTruthStudies.filter(s => s.quality !== 'high').map((study) => (
                      <option key={study.nct_id} value={study.nct_id}>
                        {study.nct_id} - {study.therapeutic_area} ({study.sap_lines} lines)
                      </option>
                    ))}
                  </optgroup>
                </select>
                <button
                  onClick={runEvaluation}
                  disabled={!selectedStudy || evaluating}
                  className={`px-6 py-2 rounded-lg font-medium transition-colors ${
                    !selectedStudy || evaluating
                      ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                      : 'bg-purple-600 text-white hover:bg-purple-700'
                  }`}
                >
                  {evaluating ? 'Evaluating...' : 'Compare'}
                </button>
              </div>

              {/* Error */}
              {evalError && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm mb-4">
                  {evalError}
                </div>
              )}

              {/* Evaluation Results */}
              {evaluation && (
                <div className="space-y-4">
                  {/* Metrics Grid */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div className="bg-white rounded-lg p-3 border">
                      <p className="text-xs text-gray-500 uppercase">Section Coverage</p>
                      <p className="text-xl font-bold text-purple-600">{evaluation.section_coverage_pct}%</p>
                    </div>
                    <div className="bg-white rounded-lg p-3 border">
                      <p className="text-xs text-gray-500 uppercase">Keyword Match</p>
                      <p className="text-xl font-bold text-purple-600">{evaluation.keyword_overlap_pct}%</p>
                    </div>
                    <div className="bg-white rounded-lg p-3 border">
                      <p className="text-xs text-gray-500 uppercase">Ground Truth</p>
                      <p className="text-xl font-bold text-gray-700">{evaluation.ground_truth_lines} lines</p>
                    </div>
                    <div className="bg-white rounded-lg p-3 border">
                      <p className="text-xs text-gray-500 uppercase">Generated</p>
                      <p className="text-xl font-bold text-gray-700">{evaluation.generated_lines} lines</p>
                    </div>
                  </div>

                  {/* Structure Checklist */}
                  <div className="bg-white rounded-lg p-4 border">
                    <p className="text-sm font-medium text-gray-700 mb-3">Structure Checklist</p>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
                      {[
                        { label: 'Primary Endpoint', value: evaluation.has_primary_endpoint },
                        { label: 'Secondary Endpoint', value: evaluation.has_secondary_endpoint },
                        { label: 'Sample Size', value: evaluation.has_sample_size },
                        { label: 'Analysis Populations', value: evaluation.has_analysis_populations },
                        { label: 'Statistical Methods', value: evaluation.has_statistical_methods },
                        { label: 'Missing Data', value: evaluation.has_missing_data },
                      ].map((item) => (
                        <div key={item.label} className="flex items-center gap-2">
                          <span className={item.value ? 'text-green-500' : 'text-red-400'}>
                            {item.value ? '✓' : '✗'}
                          </span>
                          <span className={item.value ? 'text-gray-700' : 'text-gray-400'}>{item.label}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Missing Sections */}
                  {evaluation.sections_missing.length > 0 && (
                    <div className="bg-yellow-50 rounded-lg p-3 border border-yellow-200">
                      <p className="text-sm font-medium text-yellow-800 mb-1">Missing Sections:</p>
                      <p className="text-sm text-yellow-700">{evaluation.sections_missing.join(', ')}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Batch Evaluation Section */}
              <div className="mt-4 pt-4 border-t border-purple-200">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">📊</span>
                    <h4 className="font-medium text-gray-800">Batch Evaluation</h4>
                  </div>
                  <div className="flex items-center gap-2">
                    <select
                      value={batchLimit}
                      onChange={(e) => setBatchLimit(Number(e.target.value))}
                      disabled={batchEvaluating}
                      className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value={10}>10 studies</option>
                      <option value={30}>30 studies</option>
                      <option value={50}>50 studies</option>
                      <option value={100}>100 studies</option>
                      <option value={500}>All ({groundTruthStudies.length})</option>
                    </select>
                    <button
                      onClick={runBatchEvaluation}
                      disabled={batchEvaluating}
                      className={`px-4 py-2 rounded-lg font-medium text-sm transition-colors ${
                        batchEvaluating
                          ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                          : 'bg-indigo-600 text-white hover:bg-indigo-700'
                      }`}
                    >
                      {batchEvaluating ? 'Running...' : 'Run Batch'}
                    </button>
                  </div>
                </div>

                {/* Batch Error */}
                {batchError && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm mb-3">
                    {batchError}
                  </div>
                )}

                {/* Batch Results */}
                {batchEvaluation && (
                  <div className="space-y-3">
                    {/* Aggregate Score */}
                    <div className="flex items-center gap-4 p-4 bg-white rounded-lg border">
                      <div className={`px-5 py-3 rounded-xl font-bold text-2xl ${
                        batchEvaluation.aggregate.avg_overall_score >= 70 ? 'bg-green-100 text-green-700' :
                        batchEvaluation.aggregate.avg_overall_score >= 50 ? 'bg-yellow-100 text-yellow-700' :
                        'bg-red-100 text-red-700'
                      }`}>
                        {batchEvaluation.aggregate.avg_overall_score}%
                      </div>
                      <div>
                        <p className="font-semibold text-gray-900">Average Accuracy Score</p>
                        <p className="text-sm text-gray-500">Across {batchEvaluation.total_comparisons} ground truth SAPs</p>
                      </div>
                    </div>

                    {/* Metrics Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <div className="bg-white rounded-lg p-3 border text-center">
                        <p className="text-xs text-gray-500 uppercase">Avg Section Coverage</p>
                        <p className="text-xl font-bold text-indigo-600">{batchEvaluation.aggregate.avg_section_coverage_pct}%</p>
                      </div>
                      <div className="bg-white rounded-lg p-3 border text-center">
                        <p className="text-xs text-gray-500 uppercase">Avg Keyword Match</p>
                        <p className="text-xl font-bold text-indigo-600">{batchEvaluation.aggregate.avg_keyword_overlap_pct}%</p>
                      </div>
                      <div className="bg-white rounded-lg p-3 border text-center">
                        <p className="text-xs text-gray-500 uppercase">Has Primary Endpoint</p>
                        <p className="text-xl font-bold text-green-600">{batchEvaluation.aggregate.primary_endpoint_pct}%</p>
                      </div>
                      <div className="bg-white rounded-lg p-3 border text-center">
                        <p className="text-xs text-gray-500 uppercase">Has Stats Methods</p>
                        <p className="text-xl font-bold text-green-600">{batchEvaluation.aggregate.statistical_methods_pct}%</p>
                      </div>
                    </div>

                    {/* Best/Worst Match */}
                    <div className="grid grid-cols-2 gap-3">
                      {batchEvaluation.best_match && (
                        <div className="bg-green-50 rounded-lg p-3 border border-green-200">
                          <p className="text-xs text-green-600 uppercase font-medium">Best Match</p>
                          <p className="font-semibold text-green-800">{batchEvaluation.best_match.nct_id}</p>
                          <p className="text-sm text-green-700">Score: {batchEvaluation.best_match.overall_score}%</p>
                        </div>
                      )}
                      {batchEvaluation.worst_match && (
                        <div className="bg-orange-50 rounded-lg p-3 border border-orange-200">
                          <p className="text-xs text-orange-600 uppercase font-medium">Lowest Match</p>
                          <p className="font-semibold text-orange-800">{batchEvaluation.worst_match.nct_id}</p>
                          <p className="text-sm text-orange-700">Score: {batchEvaluation.worst_match.overall_score}%</p>
                        </div>
                      )}
                    </div>

                    {/* Expandable Details */}
                    <button
                      onClick={() => setShowBatchDetails(!showBatchDetails)}
                      className="text-sm text-indigo-600 hover:text-indigo-800 font-medium"
                    >
                      {showBatchDetails ? '▼ Hide Details' : '▶ Show All Results'}
                    </button>

                    {showBatchDetails && (
                      <div className="max-h-64 overflow-y-auto bg-white rounded-lg border">
                        <table className="w-full text-sm">
                          <thead className="bg-gray-50 sticky top-0">
                            <tr>
                              <th className="px-3 py-2 text-left font-medium text-gray-600">NCT ID</th>
                              <th className="px-3 py-2 text-left font-medium text-gray-600">Quality</th>
                              <th className="px-3 py-2 text-right font-medium text-gray-600">Score</th>
                              <th className="px-3 py-2 text-right font-medium text-gray-600">Sections</th>
                              <th className="px-3 py-2 text-right font-medium text-gray-600">Keywords</th>
                            </tr>
                          </thead>
                          <tbody>
                            {batchEvaluation.results.map((r, i) => (
                              <tr key={r.nct_id} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                <td className="px-3 py-2 font-mono text-xs">{r.nct_id}</td>
                                <td className="px-3 py-2">
                                  <span className={`text-xs px-2 py-0.5 rounded ${r.quality === 'high' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'}`}>
                                    {r.quality}
                                  </span>
                                </td>
                                <td className={`px-3 py-2 text-right font-medium ${r.overall_score >= 70 ? 'text-green-600' : r.overall_score >= 50 ? 'text-yellow-600' : 'text-red-600'}`}>
                                  {r.overall_score}%
                                </td>
                                <td className="px-3 py-2 text-right text-gray-600">{r.section_coverage_pct}%</td>
                                <td className="px-3 py-2 text-right text-gray-600">{r.keyword_overlap_pct}%</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-white rounded-xl shadow-sm border p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide">Quality Score</p>
              <p className="text-2xl font-bold text-indigo-600 mt-1">
                {result.quality_score?.toFixed(0) || '-'}<span className="text-sm font-normal text-gray-400">/100</span>
              </p>
            </div>
            <div className="bg-white rounded-xl shadow-sm border p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide">Endpoint Type</p>
              <p className="text-lg font-semibold text-gray-900 mt-1">{result.endpoint_type || 'N/A'}</p>
            </div>
            <div className="bg-white rounded-xl shadow-sm border p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide">Phase</p>
              <p className="text-lg font-semibold text-gray-900 mt-1">{result.phase || 'N/A'}</p>
            </div>
            <div className="bg-white rounded-xl shadow-sm border p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide">Therapeutic Area</p>
              <p className="text-lg font-semibold text-gray-900 mt-1 truncate">{result.therapeutic_area || 'N/A'}</p>
            </div>
            <div className="bg-white rounded-xl shadow-sm border p-4">
              <p className="text-xs text-gray-500 uppercase tracking-wide">Processing Time</p>
              <p className="text-lg font-semibold text-gray-900 mt-1">{result.processing_time?.toFixed(1) || '-'}s</p>
            </div>
          </div>

          {/* Tabs */}
          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <div className="border-b flex flex-wrap">
              <button
                onClick={() => setActiveTab('sap')}
                className={`flex-1 min-w-[100px] py-3 px-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'sap'
                    ? 'border-indigo-600 text-indigo-600 bg-indigo-50'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                📄 SAP
              </button>
              <button
                onClick={() => setActiveTab('sdtm')}
                className={`flex-1 min-w-[100px] py-3 px-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'sdtm'
                    ? 'border-indigo-600 text-indigo-600 bg-indigo-50'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                🗃️ SDTM {sdtmSpec && <span className="ml-1 text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full">{sdtmSpec.domain_count}</span>}
              </button>
              <button
                onClick={() => setActiveTab('tlf')}
                className={`flex-1 min-w-[100px] py-3 px-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'tlf'
                    ? 'border-indigo-600 text-indigo-600 bg-indigo-50'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                📊 TLF {tlfResult && <span className="ml-1 text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full">{tlfResult.total_outputs}</span>}
              </button>
              <button
                onClick={() => setActiveTab('adam')}
                className={`flex-1 min-w-[100px] py-3 px-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'adam'
                    ? 'border-indigo-600 text-indigo-600 bg-indigo-50'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                📐 ADaM {adamResult && <span className="ml-1 text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full">{adamResult.datasets.length}</span>}
              </button>
              <button
                onClick={() => setActiveTab('definexml')}
                className={`flex-1 min-w-[100px] py-3 px-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'definexml'
                    ? 'border-indigo-600 text-indigo-600 bg-indigo-50'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                📋 Define-XML {defineXmlResult && <span className="ml-1 text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full">✓</span>}
              </button>
              <button
                onClick={() => setActiveTab('protocol')}
                className={`flex-1 min-w-[100px] py-3 px-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'protocol'
                    ? 'border-indigo-600 text-indigo-600 bg-indigo-50'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                📝 Protocol
              </button>
            </div>

            {/* Tab Content */}
            <div className="p-6">
              {activeTab === 'sap' && result.generated_sap && (
                <div>
                  <div className="flex justify-end mb-4 gap-2">
                    <button
                      onClick={() => downloadTextFile(result.generated_sap || '', `SAP_${result.filename || jobId.slice(0, 8)}.md`)}
                      className="text-sm bg-indigo-600 text-white py-2 px-4 rounded-lg hover:bg-indigo-700 transition-colors"
                    >
                      Download Markdown
                    </button>
                    <button
                      onClick={() => {
                        navigator.clipboard.writeText(result.generated_sap || '')
                      }}
                      className="text-sm border border-gray-300 text-gray-700 py-2 px-4 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      Copy to Clipboard
                    </button>
                  </div>
                  <div className="prose max-w-none markdown-body overflow-auto max-h-[600px] border rounded-lg p-6 bg-gray-50">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.generated_sap}</ReactMarkdown>
                  </div>
                </div>
              )}

              {activeTab === 'sdtm' && (
                <div>
                  {/* Generate Button */}
                  {!sdtmSpec && !sdtmLoading && (
                    <div className="text-center py-8">
                      <div className="text-4xl mb-4">🗃️</div>
                      <h3 className="text-lg font-semibold text-gray-900 mb-2">Generate SDTM Specifications</h3>
                      <p className="text-gray-600 mb-6 max-w-md mx-auto">
                        Generate CDISC-compliant SDTM domain specifications based on the protocol and SAP.
                      </p>
                      <button
                        onClick={generateSdtmSpecs}
                        className="bg-indigo-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-indigo-700 transition-colors"
                      >
                        Generate SDTM Specs
                      </button>
                    </div>
                  )}

                  {/* Loading State */}
                  {sdtmLoading && (
                    <div className="text-center py-8">
                      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
                      <p className="text-gray-600">Generating SDTM specifications...</p>
                    </div>
                  )}

                  {/* Error State */}
                  {sdtmError && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                      <p className="text-red-700">{sdtmError}</p>
                      <button
                        onClick={generateSdtmSpecs}
                        className="mt-2 text-sm text-red-600 hover:text-red-800 font-medium"
                      >
                        Try Again
                      </button>
                    </div>
                  )}

                  {/* SDTM Results */}
                  {sdtmSpec && (
                    <div className="space-y-4">
                      {/* Header */}
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="text-lg font-semibold text-gray-900">
                            SDTM Specification v{sdtmSpec.sdtm_version}
                          </h3>
                          <p className="text-sm text-gray-500">{sdtmSpec.message}</p>
                        </div>
                        <button
                          onClick={() => downloadTextFile(sdtmSpec.markdown || '', `SDTM_Spec_${result?.filename || jobId.slice(0, 8)}.md`)}
                          className="text-sm bg-indigo-600 text-white py-2 px-4 rounded-lg hover:bg-indigo-700 transition-colors"
                        >
                          Download Markdown
                        </button>
                      </div>

                      {/* SAP Summary - Extracted Information */}
                      {sdtmSpec.sap_summary && (
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                          <h4 className="font-semibold text-blue-900 mb-2 flex items-center gap-2">
                            <span className="text-lg">📋</span> Extracted from SAP
                          </h4>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                            {sdtmSpec.sap_summary.primary_endpoint && (
                              <div>
                                <span className="font-medium text-blue-800">Primary Endpoint:</span>
                                <p className="text-blue-700 mt-0.5">{sdtmSpec.sap_summary.primary_endpoint}</p>
                              </div>
                            )}
                            {sdtmSpec.sap_summary.primary_timepoint && (
                              <div>
                                <span className="font-medium text-blue-800">Primary Timepoint:</span>
                                <p className="text-blue-700 mt-0.5">{sdtmSpec.sap_summary.primary_timepoint}</p>
                              </div>
                            )}
                            {sdtmSpec.sap_summary.populations && sdtmSpec.sap_summary.populations.length > 0 && (
                              <div>
                                <span className="font-medium text-blue-800">Analysis Populations:</span>
                                <p className="text-blue-700 mt-0.5">{sdtmSpec.sap_summary.populations.join(', ')}</p>
                              </div>
                            )}
                            {sdtmSpec.sap_summary.sample_size && (
                              <div>
                                <span className="font-medium text-blue-800">Sample Size:</span>
                                <p className="text-blue-700 mt-0.5">{sdtmSpec.sap_summary.sample_size} subjects</p>
                              </div>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Domain Cards */}
                      <div className="grid gap-3">
                        {sdtmSpec.domains.map((domain) => (
                          <div key={domain.code} className="border rounded-lg overflow-hidden">
                            <button
                              onClick={() => setExpandedDomain(expandedDomain === domain.code ? null : domain.code)}
                              className="w-full px-4 py-3 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
                            >
                              <div className="flex items-center gap-3">
                                <span className="font-mono text-sm font-bold bg-indigo-100 text-indigo-700 px-2 py-1 rounded">
                                  {domain.code}
                                </span>
                                <div className="text-left">
                                  <p className="font-medium text-gray-900">{domain.name}</p>
                                  <p className="text-xs text-gray-500">
                                    {domain.class} • {domain.variables.length} variables
                                    {domain.traceability && domain.traceability.length > 0 && (
                                      <span className="ml-2 inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                                        {domain.traceability.length} SAP links
                                      </span>
                                    )}
                                  </p>
                                </div>
                              </div>
                              <span className="text-gray-400">{expandedDomain === domain.code ? '▼' : '▶'}</span>
                            </button>

                            {expandedDomain === domain.code && (
                              <div className="p-4 border-t bg-white">
                                <p className="text-sm text-gray-600 mb-3">{domain.purpose}</p>
                                <p className="text-xs text-gray-500 mb-3">Structure: {domain.structure}</p>

                                {/* SAP Traceability */}
                                {domain.traceability && domain.traceability.length > 0 && (
                                  <div className="mb-4 bg-green-50 border border-green-200 rounded-lg p-3">
                                    <h5 className="text-sm font-medium text-green-800 mb-2">SAP Traceability</h5>
                                    <div className="space-y-2">
                                      {domain.traceability.map((trace, idx) => (
                                        <div key={idx} className="text-xs">
                                          <span className="font-medium text-green-700">{trace.sap_section}:</span>
                                          <span className="text-green-600 ml-1">{trace.sdtm_element}</span>
                                          <p className="text-green-500 ml-2 mt-0.5 italic">&quot;{trace.sap_text.slice(0, 100)}{trace.sap_text.length > 100 ? '...' : ''}&quot;</p>
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                )}

                                {/* Study-Specific Notes */}
                                {domain.study_specific_notes && domain.study_specific_notes.length > 0 && (
                                  <div className="mb-4 bg-amber-50 border border-amber-200 rounded-lg p-3">
                                    <h5 className="text-sm font-medium text-amber-800 mb-1">Study-Specific Requirements</h5>
                                    <ul className="text-xs text-amber-700 list-disc list-inside">
                                      {domain.study_specific_notes.map((note, idx) => (
                                        <li key={idx}>{note}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}

                                {/* Variables Table */}
                                <div className="overflow-x-auto">
                                  <table className="w-full text-sm">
                                    <thead className="bg-gray-50">
                                      <tr>
                                        <th className="px-3 py-2 text-left font-medium text-gray-600">Variable</th>
                                        <th className="px-3 py-2 text-left font-medium text-gray-600">Label</th>
                                        <th className="px-3 py-2 text-center font-medium text-gray-600">Type</th>
                                        <th className="px-3 py-2 text-center font-medium text-gray-600">Core</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {domain.variables.map((v, i) => (
                                        <tr key={v.name} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                          <td className="px-3 py-2 font-mono text-xs font-medium text-gray-900">{v.name}</td>
                                          <td className="px-3 py-2 text-gray-700">{v.label}</td>
                                          <td className="px-3 py-2 text-center text-gray-600">{v.type}</td>
                                          <td className="px-3 py-2 text-center">
                                            <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                                              v.core === 'Req' ? 'bg-red-100 text-red-700' :
                                              v.core === 'Exp' ? 'bg-yellow-100 text-yellow-700' :
                                              'bg-gray-100 text-gray-600'
                                            }`}>
                                              {v.core}
                                            </span>
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>

                      {/* Legend */}
                      <div className="flex items-center gap-4 text-xs text-gray-500 pt-2 border-t">
                        <span>Core Classifications:</span>
                        <span className="flex items-center gap-1">
                          <span className="bg-red-100 text-red-700 px-1.5 py-0.5 rounded font-medium">Req</span> Required
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded font-medium">Exp</span> Expected
                        </span>
                        <span className="flex items-center gap-1">
                          <span className="bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded font-medium">Perm</span> Permissible
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* TLF Shells Tab */}
              {activeTab === 'tlf' && (
                <div>
                  {/* Generate Button */}
                  {!tlfResult && !tlfLoading && (
                    <div className="text-center py-8">
                      <div className="text-4xl mb-4">📊</div>
                      <h3 className="text-lg font-semibold text-gray-900 mb-2">Generate TLF Shells</h3>
                      <p className="text-gray-600 mb-6 max-w-md mx-auto">
                        Generate Tables, Listings, and Figures shell specifications based on the SAP.
                      </p>
                      <button
                        onClick={generateTlfShells}
                        className="bg-indigo-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-indigo-700 transition-colors"
                      >
                        Generate TLF Shells
                      </button>
                    </div>
                  )}

                  {/* Loading State */}
                  {tlfLoading && (
                    <div className="text-center py-8">
                      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
                      <p className="text-gray-600">Generating TLF shells...</p>
                    </div>
                  )}

                  {/* Error State */}
                  {tlfError && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                      <p className="text-red-700">{tlfError}</p>
                      <button
                        onClick={generateTlfShells}
                        className="mt-2 text-sm text-red-600 hover:text-red-800 font-medium"
                      >
                        Try Again
                      </button>
                    </div>
                  )}

                  {/* TLF Results */}
                  {tlfResult && (
                    <div className="space-y-4">
                      {/* Header */}
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="text-lg font-semibold text-gray-900">TLF Shell Specifications</h3>
                          <p className="text-sm text-gray-500">{tlfResult.message}</p>
                        </div>
                        <button
                          onClick={() => downloadTextFile(tlfResult.markdown || '', `TLF_Shells_${result?.filename || jobId.slice(0, 8)}.md`)}
                          className="text-sm bg-indigo-600 text-white py-2 px-4 rounded-lg hover:bg-indigo-700 transition-colors"
                        >
                          Download Markdown
                        </button>
                      </div>

                      {/* Summary Cards */}
                      <div className="grid grid-cols-3 gap-4">
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
                          <p className="text-2xl font-bold text-blue-700">{tlfResult.tables.length}</p>
                          <p className="text-sm text-blue-600">Tables</p>
                        </div>
                        <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
                          <p className="text-2xl font-bold text-green-700">{tlfResult.listings.length}</p>
                          <p className="text-sm text-green-600">Listings</p>
                        </div>
                        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 text-center">
                          <p className="text-2xl font-bold text-purple-700">{tlfResult.figures.length}</p>
                          <p className="text-sm text-purple-600">Figures</p>
                        </div>
                      </div>

                      {/* Tables Section */}
                      {tlfResult.tables.length > 0 && (
                        <div>
                          <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                            <span className="bg-blue-100 text-blue-700 px-2 py-1 rounded text-xs">TABLES</span>
                          </h4>
                          <div className="space-y-2">
                            {tlfResult.tables.map((table) => (
                              <div key={table.output_id} className="border rounded-lg p-3 hover:bg-gray-50">
                                <div className="flex items-center justify-between">
                                  <div>
                                    <span className="font-mono text-sm font-medium text-gray-900">{table.output_id}</span>
                                    <p className="text-sm text-gray-600">{table.title}</p>
                                  </div>
                                  <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">{table.population}</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Listings Section */}
                      {tlfResult.listings.length > 0 && (
                        <div>
                          <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                            <span className="bg-green-100 text-green-700 px-2 py-1 rounded text-xs">LISTINGS</span>
                          </h4>
                          <div className="space-y-2">
                            {tlfResult.listings.map((listing) => (
                              <div key={listing.output_id} className="border rounded-lg p-3 hover:bg-gray-50">
                                <span className="font-mono text-sm font-medium text-gray-900">{listing.output_id}</span>
                                <p className="text-sm text-gray-600">{listing.title}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Figures Section */}
                      {tlfResult.figures.length > 0 && (
                        <div>
                          <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                            <span className="bg-purple-100 text-purple-700 px-2 py-1 rounded text-xs">FIGURES</span>
                          </h4>
                          <div className="space-y-2">
                            {tlfResult.figures.map((figure) => (
                              <div key={figure.output_id} className="border rounded-lg p-3 hover:bg-gray-50">
                                <span className="font-mono text-sm font-medium text-gray-900">{figure.output_id}</span>
                                <p className="text-sm text-gray-600">{figure.title}</p>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* ADaM Specs Tab */}
              {activeTab === 'adam' && (
                <div>
                  {/* Generate Button */}
                  {!adamResult && !adamLoading && (
                    <div className="text-center py-8">
                      <div className="text-4xl mb-4">📐</div>
                      <h3 className="text-lg font-semibold text-gray-900 mb-2">Generate ADaM Derivation Specs</h3>
                      <p className="text-gray-600 mb-6 max-w-md mx-auto">
                        Generate Analysis Data Model (ADaM) variable derivation specifications.
                      </p>
                      <button
                        onClick={generateAdamSpecs}
                        className="bg-indigo-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-indigo-700 transition-colors"
                      >
                        Generate ADaM Specs
                      </button>
                    </div>
                  )}

                  {/* Loading State */}
                  {adamLoading && (
                    <div className="text-center py-8">
                      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
                      <p className="text-gray-600">Generating ADaM derivation specs...</p>
                    </div>
                  )}

                  {/* Error State */}
                  {adamError && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                      <p className="text-red-700">{adamError}</p>
                      <button
                        onClick={generateAdamSpecs}
                        className="mt-2 text-sm text-red-600 hover:text-red-800 font-medium"
                      >
                        Try Again
                      </button>
                    </div>
                  )}

                  {/* ADaM Results */}
                  {adamResult && (
                    <div className="space-y-4">
                      {/* Header */}
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="text-lg font-semibold text-gray-900">ADaM Derivation Specifications</h3>
                          <p className="text-sm text-gray-500">{adamResult.message}</p>
                        </div>
                        <button
                          onClick={() => downloadTextFile(adamResult.markdown || '', `ADaM_Specs_${result?.filename || jobId.slice(0, 8)}.md`)}
                          className="text-sm bg-indigo-600 text-white py-2 px-4 rounded-lg hover:bg-indigo-700 transition-colors"
                        >
                          Download Markdown
                        </button>
                      </div>

                      {/* Summary */}
                      <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4 flex items-center justify-between">
                        <div className="flex items-center gap-4">
                          <div className="text-center">
                            <p className="text-2xl font-bold text-indigo-700">{adamResult.datasets.length}</p>
                            <p className="text-xs text-indigo-600">Datasets</p>
                          </div>
                          <div className="text-center">
                            <p className="text-2xl font-bold text-indigo-700">{adamResult.total_variables}</p>
                            <p className="text-xs text-indigo-600">Variables</p>
                          </div>
                        </div>
                      </div>

                      {/* Dataset Cards */}
                      <div className="grid gap-3">
                        {adamResult.datasets.map((dataset) => (
                          <div key={dataset.name} className="border rounded-lg overflow-hidden">
                            <button
                              onClick={() => setExpandedDataset(expandedDataset === dataset.name ? null : dataset.name)}
                              className="w-full px-4 py-3 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
                            >
                              <div className="flex items-center gap-3">
                                <span className="font-mono text-sm font-bold bg-indigo-100 text-indigo-700 px-2 py-1 rounded">
                                  {dataset.name}
                                </span>
                                <div className="text-left">
                                  <p className="font-medium text-gray-900">{dataset.label}</p>
                                  <p className="text-xs text-gray-500">
                                    {dataset.structure} • {dataset.variables.length} variables
                                  </p>
                                </div>
                              </div>
                              <span className="text-gray-400">{expandedDataset === dataset.name ? '▼' : '▶'}</span>
                            </button>

                            {expandedDataset === dataset.name && (
                              <div className="p-4 border-t bg-white">
                                <p className="text-xs text-gray-500 mb-3">Keys: {dataset.keys.join(', ')}</p>

                                {/* Variables Table */}
                                <div className="overflow-x-auto">
                                  <table className="w-full text-sm">
                                    <thead className="bg-gray-50">
                                      <tr>
                                        <th className="px-3 py-2 text-left font-medium text-gray-600">Variable</th>
                                        <th className="px-3 py-2 text-left font-medium text-gray-600">Label</th>
                                        <th className="px-3 py-2 text-left font-medium text-gray-600">Derivation</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {dataset.variables.slice(0, 15).map((v, i) => (
                                        <tr key={v.name} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                          <td className="px-3 py-2 font-mono text-xs font-medium text-gray-900">{v.name}</td>
                                          <td className="px-3 py-2 text-gray-700 text-xs">{v.label}</td>
                                          <td className="px-3 py-2 text-gray-600 text-xs">{v.derivation.slice(0, 60)}...</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                  {dataset.variables.length > 15 && (
                                    <p className="text-xs text-gray-500 text-center py-2">
                                      ...and {dataset.variables.length - 15} more variables
                                    </p>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Define-XML Tab */}
              {activeTab === 'definexml' && (
                <div>
                  {/* Generate Button */}
                  {!defineXmlResult && !defineXmlLoading && (
                    <div className="text-center py-8">
                      <div className="text-4xl mb-4">📋</div>
                      <h3 className="text-lg font-semibold text-gray-900 mb-2">Generate Define-XML</h3>
                      <p className="text-gray-600 mb-4 max-w-md mx-auto">
                        Generate CDISC Define-XML 2.1 compliant metadata for regulatory submission.
                      </p>

                      {/* Standard Selector */}
                      <div className="flex items-center justify-center gap-4 mb-6">
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="radio"
                            name="standard"
                            checked={defineXmlStandard === 'adam'}
                            onChange={() => setDefineXmlStandard('adam')}
                            className="w-4 h-4 text-indigo-600"
                          />
                          <span className="text-sm text-gray-700">ADaM (Analysis)</span>
                        </label>
                        <label className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="radio"
                            name="standard"
                            checked={defineXmlStandard === 'sdtm'}
                            onChange={() => setDefineXmlStandard('sdtm')}
                            className="w-4 h-4 text-indigo-600"
                          />
                          <span className="text-sm text-gray-700">SDTM (Tabulation)</span>
                        </label>
                      </div>

                      <button
                        onClick={generateDefineXml}
                        className="bg-indigo-600 text-white py-3 px-6 rounded-lg font-medium hover:bg-indigo-700 transition-colors"
                      >
                        Generate Define-XML
                      </button>
                    </div>
                  )}

                  {/* Loading State */}
                  {defineXmlLoading && (
                    <div className="text-center py-8">
                      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
                      <p className="text-gray-600">Generating Define-XML...</p>
                    </div>
                  )}

                  {/* Error State */}
                  {defineXmlError && (
                    <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                      <p className="text-red-700">{defineXmlError}</p>
                      <button
                        onClick={generateDefineXml}
                        className="mt-2 text-sm text-red-600 hover:text-red-800 font-medium"
                      >
                        Try Again
                      </button>
                    </div>
                  )}

                  {/* Define-XML Results */}
                  {defineXmlResult && (
                    <div className="space-y-4">
                      {/* Header */}
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="text-lg font-semibold text-gray-900">Define-XML 2.1 Metadata</h3>
                          <p className="text-sm text-gray-500">{defineXmlResult.message}</p>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => downloadTextFile(defineXmlResult.xml_content || '', `define_${defineXmlResult.standard_type.toLowerCase()}_${result?.filename || jobId.slice(0, 8)}.xml`)}
                            className="text-sm bg-indigo-600 text-white py-2 px-4 rounded-lg hover:bg-indigo-700 transition-colors"
                          >
                            Download XML
                          </button>
                          <button
                            onClick={() => {
                              setDefineXmlResult(null)
                              setDefineXmlStandard(defineXmlStandard === 'adam' ? 'sdtm' : 'adam')
                            }}
                            className="text-sm border border-gray-300 text-gray-700 py-2 px-4 rounded-lg hover:bg-gray-50 transition-colors"
                          >
                            Generate {defineXmlStandard === 'adam' ? 'SDTM' : 'ADaM'}
                          </button>
                        </div>
                      </div>

                      {/* Summary Cards */}
                      <div className="grid grid-cols-3 gap-4">
                        <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4 text-center">
                          <p className="text-2xl font-bold text-indigo-700">{defineXmlResult.standard_type}</p>
                          <p className="text-sm text-indigo-600">Standard</p>
                        </div>
                        <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
                          <p className="text-2xl font-bold text-green-700">{defineXmlResult.dataset_count}</p>
                          <p className="text-sm text-green-600">Datasets</p>
                        </div>
                        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 text-center">
                          <p className="text-2xl font-bold text-purple-700">{defineXmlResult.variable_count}</p>
                          <p className="text-sm text-purple-600">Variables</p>
                        </div>
                      </div>

                      {/* XML Preview */}
                      <div className="border rounded-lg overflow-hidden">
                        <div className="bg-gray-100 px-4 py-2 border-b flex items-center justify-between">
                          <span className="text-sm font-medium text-gray-700">XML Preview</span>
                          <span className="text-xs text-gray-500">
                            {(defineXmlResult.xml_content?.length || 0).toLocaleString()} characters
                          </span>
                        </div>
                        <pre className="p-4 bg-gray-50 overflow-auto max-h-[400px] text-xs font-mono text-gray-700">
                          {defineXmlResult.xml_content?.slice(0, 5000)}
                          {(defineXmlResult.xml_content?.length || 0) > 5000 && '\n\n... (truncated - download for full XML)'}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'protocol' && (
                <div className="prose max-w-none overflow-auto max-h-[600px] border rounded-lg p-6 bg-gray-50">
                  <pre className="whitespace-pre-wrap text-sm text-gray-700 font-mono">
                    {result.protocol_preview || 'Protocol text not available'}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

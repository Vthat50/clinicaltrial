'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

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

export default function JobDetailPage() {
  const params = useParams()
  const router = useRouter()
  const jobId = params.id as string

  const [result, setResult] = useState<JobResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'sap' | 'protocol'>('sap')

  // Evaluation state
  const [groundTruthStudies, setGroundTruthStudies] = useState<GroundTruthStudy[]>([])
  const [selectedStudy, setSelectedStudy] = useState<string>('')
  const [evaluation, setEvaluation] = useState<EvaluationResult | null>(null)
  const [evaluating, setEvaluating] = useState(false)
  const [evalError, setEvalError] = useState<string | null>(null)

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
            <div className="border-b flex">
              <button
                onClick={() => setActiveTab('sap')}
                className={`flex-1 py-3 px-4 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'sap'
                    ? 'border-indigo-600 text-indigo-600 bg-indigo-50'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                📄 Generated SAP
              </button>
              <button
                onClick={() => setActiveTab('protocol')}
                className={`flex-1 py-3 px-4 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'protocol'
                    ? 'border-indigo-600 text-indigo-600 bg-indigo-50'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                📋 Source Protocol
              </button>
            </div>

            {/* Tab Content */}
            <div className="p-6">
              {activeTab === 'sap' && result.generated_sap && (
                <div>
                  <div className="flex justify-end mb-4 gap-2">
                    <button
                      onClick={() => {
                        const blob = new Blob([result.generated_sap || ''], { type: 'text/markdown' })
                        const url = URL.createObjectURL(blob)
                        const a = document.createElement('a')
                        a.href = url
                        a.download = `SAP_${result.filename || jobId.slice(0, 8)}.md`
                        a.click()
                      }}
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

'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import ReactMarkdown from 'react-markdown'

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

export default function JobDetailPage() {
  const params = useParams()
  const router = useRouter()
  const jobId = params.id as string

  const [result, setResult] = useState<JobResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'sap' | 'protocol'>('sap')

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
                    <ReactMarkdown>{result.generated_sap}</ReactMarkdown>
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

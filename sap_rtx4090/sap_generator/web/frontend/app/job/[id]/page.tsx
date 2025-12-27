'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
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
}

export default function JobDetailPage() {
  const params = useParams()
  const jobId = params.id as string

  const [result, setResult] = useState<JobResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchJob() {
      try {
        const res = await fetch(`${API_URL}/status/${jobId}`)
        if (!res.ok) throw new Error('Job not found')
        const data = await res.json()
        setResult(data)
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }

    if (jobId) fetchJob()
  }, [jobId])

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    )
  }

  if (error || !result) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6">
        <h3 className="text-lg font-medium text-red-800">Error</h3>
        <p className="mt-2 text-red-700">{error || 'Job not found'}</p>
        <Link href="/history" className="mt-4 inline-block text-indigo-600 hover:underline">
          Back to History
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="text-sm text-gray-500">
        <Link href="/history" className="hover:text-indigo-600">History</Link>
        <span className="mx-2">/</span>
        <span>Job {jobId.slice(0, 8)}...</span>
      </div>

      {/* Summary Card */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-start">
          <div>
            <h2 className="text-xl font-bold text-gray-900">
              Job Details
            </h2>
            <p className="mt-1 text-sm text-gray-500">
              Created: {result.created_at ? new Date(result.created_at).toLocaleString() : 'N/A'}
            </p>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm ${
            result.status === 'completed' ? 'bg-green-100 text-green-800' :
            result.status === 'failed' ? 'bg-red-100 text-red-800' :
            'bg-yellow-100 text-yellow-800'
          }`}>
            {result.status}
          </span>
        </div>

        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-gray-50 rounded p-3">
            <p className="text-xs text-gray-500 uppercase">Quality Score</p>
            <p className="text-lg font-semibold text-indigo-600">
              {result.quality_score?.toFixed(0) || '-'}/100
            </p>
          </div>
          <div className="bg-gray-50 rounded p-3">
            <p className="text-xs text-gray-500 uppercase">Endpoint Type</p>
            <p className="text-lg font-semibold">{result.endpoint_type || 'N/A'}</p>
          </div>
          <div className="bg-gray-50 rounded p-3">
            <p className="text-xs text-gray-500 uppercase">Phase</p>
            <p className="text-lg font-semibold">{result.phase || 'N/A'}</p>
          </div>
          <div className="bg-gray-50 rounded p-3">
            <p className="text-xs text-gray-500 uppercase">Processing Time</p>
            <p className="text-lg font-semibold">
              {result.processing_time?.toFixed(1) || '-'}s
            </p>
          </div>
        </div>

        {result.error_message && (
          <div className="mt-4 p-4 bg-red-50 rounded-lg">
            <p className="text-sm text-red-700">{result.error_message}</p>
          </div>
        )}
      </div>

      {/* SAP Document */}
      {result.generated_sap && (
        <div className="bg-white rounded-lg shadow">
          <div className="border-b p-4 flex justify-between items-center">
            <h3 className="font-medium">Generated SAP Document</h3>
            <button
              onClick={() => {
                const blob = new Blob([result.generated_sap || ''], { type: 'text/markdown' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = `SAP_${jobId.slice(0, 8)}.md`
                a.click()
              }}
              className="text-sm text-indigo-600 hover:text-indigo-800"
            >
              Download as Markdown
            </button>
          </div>
          <div className="p-6 prose max-w-none markdown-body overflow-auto max-h-[600px]">
            <ReactMarkdown>{result.generated_sap}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  )
}

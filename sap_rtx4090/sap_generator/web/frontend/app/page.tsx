'use client'

import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type JobStatus = 'idle' | 'queued' | 'processing' | 'completed' | 'failed'

interface JobResult {
  job_id: string
  status: JobStatus
  generated_sap?: string
  quality_score?: number
  endpoint_type?: string
  phase?: string
  therapeutic_area?: string
  processing_time?: number
  error_message?: string
}

export default function Home() {
  const [protocolText, setProtocolText] = useState('')
  const [nctId, setNctId] = useState('')
  const [status, setStatus] = useState<JobStatus>('idle')
  const [jobId, setJobId] = useState<string | null>(null)
  const [result, setResult] = useState<JobResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Poll for job status
  useEffect(() => {
    if (!jobId || status === 'completed' || status === 'failed') return

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_URL}/status/${jobId}`)
        const data: JobResult = await res.json()

        setResult(data)
        setStatus(data.status as JobStatus)

        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(interval)
        }
      } catch (e) {
        console.error('Polling error:', e)
      }
    }, 3000) // Poll every 3 seconds

    return () => clearInterval(interval)
  }, [jobId, status])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setResult(null)
    setStatus('queued')

    try {
      const res = await fetch(`${API_URL}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          protocol_text: protocolText,
          nct_id: nctId || null
        })
      })

      if (!res.ok) {
        throw new Error(`API error: ${res.statusText}`)
      }

      const data = await res.json()
      setJobId(data.job_id)
    } catch (e: any) {
      setError(e.message)
      setStatus('failed')
    }
  }

  const handleReset = () => {
    setProtocolText('')
    setNctId('')
    setStatus('idle')
    setJobId(null)
    setResult(null)
    setError(null)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-lg shadow p-6">
        <h1 className="text-2xl font-bold text-gray-900">Generate Statistical Analysis Plan</h1>
        <p className="mt-2 text-gray-600">
          Paste your clinical trial protocol text below to generate an ICH E9(R1) compliant SAP.
        </p>
      </div>

      {/* Input Form */}
      {status === 'idle' && (
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-4">
          <div>
            <label htmlFor="nctId" className="block text-sm font-medium text-gray-700">
              NCT ID (optional)
            </label>
            <input
              type="text"
              id="nctId"
              value={nctId}
              onChange={(e) => setNctId(e.target.value)}
              placeholder="e.g., NCT12345678"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2"
            />
          </div>

          <div>
            <label htmlFor="protocol" className="block text-sm font-medium text-gray-700">
              Protocol Text
            </label>
            <textarea
              id="protocol"
              rows={15}
              value={protocolText}
              onChange={(e) => setProtocolText(e.target.value)}
              placeholder="Paste your clinical trial protocol text here..."
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm border p-2 font-mono"
              required
            />
            <p className="mt-1 text-sm text-gray-500">
              {protocolText.length.toLocaleString()} characters
            </p>
          </div>

          <button
            type="submit"
            disabled={!protocolText.trim()}
            className="w-full bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            Generate SAP
          </button>
        </form>
      )}

      {/* Processing Status */}
      {(status === 'queued' || status === 'processing') && (
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center space-x-4">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
            <div>
              <p className="text-lg font-medium text-gray-900">
                {status === 'queued' ? 'Job queued...' : 'Generating SAP...'}
              </p>
              <p className="text-sm text-gray-500">
                This typically takes 60-90 seconds. Please wait.
              </p>
            </div>
          </div>
          {jobId && (
            <p className="mt-4 text-xs text-gray-400">Job ID: {jobId}</p>
          )}
        </div>
      )}

      {/* Error Display */}
      {status === 'failed' && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <h3 className="text-lg font-medium text-red-800">Generation Failed</h3>
          <p className="mt-2 text-red-700">{error || result?.error_message || 'Unknown error'}</p>
          <button
            onClick={handleReset}
            className="mt-4 bg-red-600 text-white py-2 px-4 rounded-md hover:bg-red-700"
          >
            Try Again
          </button>
        </div>
      )}

      {/* Results Display */}
      {status === 'completed' && result && (
        <div className="space-y-6">
          {/* Summary Card */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex justify-between items-start">
              <div>
                <h2 className="text-xl font-bold text-gray-900">SAP Generated Successfully</h2>
                <p className="mt-1 text-sm text-gray-500">
                  Processed in {result.processing_time?.toFixed(1)} seconds
                </p>
              </div>
              <button
                onClick={handleReset}
                className="bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 text-sm"
              >
                Generate Another
              </button>
            </div>

            <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-gray-50 rounded p-3">
                <p className="text-xs text-gray-500 uppercase">Quality Score</p>
                <p className="text-lg font-semibold text-indigo-600">
                  {result.quality_score?.toFixed(0)}/100
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
                <p className="text-xs text-gray-500 uppercase">Therapeutic Area</p>
                <p className="text-lg font-semibold">{result.therapeutic_area || 'N/A'}</p>
              </div>
            </div>
          </div>

          {/* SAP Document */}
          <div className="bg-white rounded-lg shadow">
            <div className="border-b p-4 flex justify-between items-center">
              <h3 className="font-medium">Generated SAP Document</h3>
              <button
                onClick={() => {
                  const blob = new Blob([result.generated_sap || ''], { type: 'text/markdown' })
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url
                  a.download = `SAP_${nctId || 'document'}.md`
                  a.click()
                }}
                className="text-sm text-indigo-600 hover:text-indigo-800"
              >
                Download as Markdown
              </button>
            </div>
            <div className="p-6 prose max-w-none markdown-body overflow-auto max-h-[600px]">
              <ReactMarkdown>{result.generated_sap || ''}</ReactMarkdown>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

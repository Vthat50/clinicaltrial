'use client'

import { useState, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

type UploadMode = 'file' | 'text'

export default function Home() {
  const router = useRouter()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [mode, setMode] = useState<UploadMode>('file')
  const [file, setFile] = useState<File | null>(null)
  const [textInput, setTextInput] = useState('')
  const [nctId, setNctId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragActive, setDragActive] = useState(false)

  // Handle drag events
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }, [])

  // Handle drop
  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0]
      validateAndSetFile(droppedFile)
    }
  }, [])

  // Validate file
  const validateAndSetFile = (file: File) => {
    const allowedExtensions = ['pdf', 'docx', 'doc', 'txt']
    const ext = file.name.split('.').pop()?.toLowerCase()

    if (!allowedExtensions.includes(ext || '')) {
      setError('Please upload a PDF, DOCX, or TXT file')
      return
    }

    if (file.size > 10 * 1024 * 1024) {
      setError('File size must be less than 10MB')
      return
    }

    setFile(file)
    setError(null)
  }

  // Handle file selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0])
    }
  }

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      let response

      if (mode === 'file' && file) {
        // Upload file
        const formData = new FormData()
        formData.append('file', file)
        if (nctId) formData.append('nct_id', nctId)

        response = await fetch(`${API_URL}/upload`, {
          method: 'POST',
          body: formData,
        })
      } else if (mode === 'text' && textInput.trim()) {
        // Submit text
        response = await fetch(`${API_URL}/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            protocol_text: textInput,
            nct_id: nctId || null,
          }),
        })
      } else {
        throw new Error('Please provide a file or text')
      }

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Upload failed')
      }

      const data = await response.json()

      // Navigate to job status page
      router.push(`/job/${data.job_id}`)

    } catch (err: any) {
      setError(err.message || 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  // Get file icon based on type
  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase()
    if (ext === 'pdf') return '📄'
    if (ext === 'docx' || ext === 'doc') return '📝'
    return '📃'
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          SAP Generator
        </h1>
        <p className="text-gray-600">
          Upload a clinical trial protocol to generate a Statistical Analysis Plan
        </p>
      </div>

      {/* Mode Toggle */}
      <div className="flex justify-center mb-6">
        <div className="inline-flex rounded-lg border border-gray-200 p-1 bg-gray-50">
          <button
            type="button"
            onClick={() => setMode('file')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              mode === 'file'
                ? 'bg-white shadow text-indigo-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Upload File
          </button>
          <button
            type="button"
            onClick={() => setMode('text')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              mode === 'text'
                ? 'bg-white shadow text-indigo-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Paste Text
          </button>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* File Upload Mode */}
        {mode === 'file' && (
          <div
            className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
              dragActive
                ? 'border-indigo-500 bg-indigo-50'
                : file
                ? 'border-green-400 bg-green-50'
                : 'border-gray-300 hover:border-gray-400'
            }`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <input
              ref={fileInputRef}
              type="file"
              onChange={handleFileChange}
              accept=".pdf,.docx,.doc,.txt"
              className="hidden"
            />

            {file ? (
              <div className="space-y-3">
                <div className="text-4xl">{getFileIcon(file.name)}</div>
                <div>
                  <p className="font-medium text-gray-900">{file.name}</p>
                  <p className="text-sm text-gray-500">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setFile(null)}
                  className="text-sm text-red-600 hover:text-red-700"
                >
                  Remove file
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="text-4xl">📁</div>
                <div>
                  <p className="text-gray-700">
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="text-indigo-600 hover:text-indigo-700 font-medium"
                    >
                      Click to upload
                    </button>
                    {' '}or drag and drop
                  </p>
                  <p className="text-sm text-gray-500 mt-1">
                    PDF, DOCX, or TXT (max 10MB)
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Text Input Mode */}
        {mode === 'text' && (
          <div>
            <textarea
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              placeholder="Paste your clinical trial protocol text here..."
              rows={12}
              className="w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 resize-none"
            />
            <p className="text-sm text-gray-500 mt-2">
              {textInput.length.toLocaleString()} characters
            </p>
          </div>
        )}

        {/* NCT ID (Optional) */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            NCT ID (Optional)
          </label>
          <input
            type="text"
            value={nctId}
            onChange={(e) => setNctId(e.target.value)}
            placeholder="NCT00000000"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
          />
        </div>

        {/* Error Message */}
        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading || (mode === 'file' && !file) || (mode === 'text' && !textInput.trim())}
          className={`w-full py-3 px-4 rounded-xl font-medium text-white transition-colors ${
            loading
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-indigo-600 hover:bg-indigo-700'
          }`}
        >
          {loading ? (
            <span className="flex items-center justify-center">
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Processing...
            </span>
          ) : (
            'Generate SAP'
          )}
        </button>
      </form>

      {/* Features */}
      <div className="mt-12 grid grid-cols-3 gap-4 text-center">
        <div className="p-4">
          <div className="text-2xl mb-2">📄</div>
          <h3 className="font-medium text-gray-900">PDF Support</h3>
          <p className="text-sm text-gray-500">Upload protocol PDFs directly</p>
        </div>
        <div className="p-4">
          <div className="text-2xl mb-2">📝</div>
          <h3 className="font-medium text-gray-900">Word Docs</h3>
          <p className="text-sm text-gray-500">DOCX files are supported</p>
        </div>
        <div className="p-4">
          <div className="text-2xl mb-2">🤖</div>
          <h3 className="font-medium text-gray-900">AI-Powered</h3>
          <p className="text-sm text-gray-500">83% accuracy on endpoint extraction</p>
        </div>
      </div>
    </div>
  )
}

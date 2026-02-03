'use client'

import { useState, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

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

  // TLF Shells state
  const [tlfLoading, setTlfLoading] = useState(false)
  const [tlfError, setTlfError] = useState<string | null>(null)
  const [tlfMarkdown, setTlfMarkdown] = useState<string | null>(null)

  // TLF LLM state
  const [tlfLlmLoading, setTlfLlmLoading] = useState(false)
  const [tlfLlmError, setTlfLlmError] = useState<string | null>(null)
  const [tlfLlmMarkdown, setTlfLlmMarkdown] = useState<string | null>(null)

  // TLF Demo state (4 targeted items — requires protocol + SAP)
  const [tlfDemoLoading, setTlfDemoLoading] = useState(false)
  const [tlfDemoError, setTlfDemoError] = useState<string | null>(null)
  const [tlfDemoMarkdown, setTlfDemoMarkdown] = useState<string | null>(null)
  const [sapFile, setSapFile] = useState<File | null>(null)

  // TLF Skills state
  const [tlfSkills, setTlfSkills] = useState<any[]>([])
  const [selectedSkills, setSelectedSkills] = useState<Set<string>>(new Set())
  const [showSkillSelector, setShowSkillSelector] = useState(false)
  const [skillsLoading, setSkillsLoading] = useState(false)

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

  // Load skill preview — shows which skills apply and their counts
  const handleLoadSkillsPreview = async () => {
    if (mode === 'file' && !file) return
    if (mode === 'text' && !textInput.trim()) return

    setSkillsLoading(true)
    setTlfError(null)

    try {
      let fileToSend: File
      if (mode === 'file' && file) {
        fileToSend = file
      } else {
        const blob = new Blob([textInput], { type: 'text/plain' })
        fileToSend = new File([blob], 'protocol.txt', { type: 'text/plain' })
      }

      const formData = new FormData()
      formData.append('file', fileToSend)

      const res = await fetch(`${API_URL}/tlf-skills-preview`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Failed to load skills preview')
      }

      const data = await res.json()
      if (data.success && data.skills) {
        setTlfSkills(data.skills)
        // Select all skills that have content by default
        setSelectedSkills(new Set(data.skills.filter((s: any) => s.has_content).map((s: any) => s.id)))
        setShowSkillSelector(true)
      } else {
        throw new Error(data.message || 'Failed to load skills')
      }
    } catch (err: any) {
      setTlfError(err.message || 'Failed to load skills preview')
    } finally {
      setSkillsLoading(false)
    }
  }

  // Toggle a skill selection
  const toggleSkill = (skillId: string) => {
    setSelectedSkills(prev => {
      const next = new Set(prev)
      if (next.has(skillId)) {
        next.delete(skillId)
      } else {
        next.add(skillId)
      }
      return next
    })
  }

  // Select/deselect all skills
  const toggleAllSkills = () => {
    if (selectedSkills.size === tlfSkills.filter(s => s.has_content).length) {
      setSelectedSkills(new Set())
    } else {
      setSelectedSkills(new Set(tlfSkills.filter(s => s.has_content).map(s => s.id)))
    }
  }

  // Generate TLF Shells via LLM-driven system (new)
  const handleGenerateTlfLlm = async (format: 'markdown' | 'docx' = 'markdown') => {
    if (mode === 'file' && !file) return
    if (mode === 'text' && !textInput.trim()) return

    setTlfLlmLoading(true)
    setTlfLlmError(null)
    setTlfLlmMarkdown(null)

    try {
      let fileToSend: File
      if (mode === 'file' && file) {
        fileToSend = file
      } else {
        const blob = new Blob([textInput], { type: 'text/plain' })
        fileToSend = new File([blob], 'protocol.txt', { type: 'text/plain' })
      }

      const formData = new FormData()
      formData.append('file', fileToSend)

      const res = await fetch(`${API_URL}/generate-tlf-shells-llm-direct?format=${format}`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'TLF LLM generation failed')
      }

      if (format === 'docx') {
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `TLF_Shells_LLM_${mode === 'file' && file ? file.name.replace(/\.[^/.]+$/, '') : 'protocol'}.docx`
        a.click()
        URL.revokeObjectURL(url)
      } else {
        const data = await res.json()
        if (data.success) {
          setTlfLlmMarkdown(data.markdown)
        } else {
          throw new Error(data.message || 'TLF LLM generation failed')
        }
      }
    } catch (err: any) {
      setTlfLlmError(err.message || 'TLF LLM generation failed')
    } finally {
      setTlfLlmLoading(false)
    }
  }

  // Generate Demo TLF Shells (requires protocol + SAP .docx)
  const handleGenerateTlfDemo = async (format: 'markdown' | 'docx' = 'markdown') => {
    // Need the protocol (main file upload) and the SAP file
    if (mode === 'file' && !file) {
      setTlfDemoError('Please upload a protocol file first.')
      return
    }
    if (mode === 'text' && !textInput.trim()) {
      setTlfDemoError('Please enter protocol text first.')
      return
    }
    if (!sapFile) {
      setTlfDemoError('Please upload the generated SAP .docx file.')
      return
    }

    setTlfDemoLoading(true)
    setTlfDemoError(null)
    setTlfDemoMarkdown(null)

    try {
      let protocolFile: File
      if (mode === 'file' && file) {
        protocolFile = file
      } else {
        const blob = new Blob([textInput], { type: 'text/plain' })
        protocolFile = new File([blob], 'protocol.txt', { type: 'text/plain' })
      }

      const formData = new FormData()
      formData.append('protocol_file', protocolFile)
      formData.append('sap_file', sapFile)

      const res = await fetch(`${API_URL}/generate-tlf-demo-direct?format=${format}`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'TLF Demo generation failed')
      }

      if (format === 'docx') {
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `TLF_Demo_${sapFile.name.replace(/\.[^/.]+$/, '')}.docx`
        a.click()
        URL.revokeObjectURL(url)
      } else {
        const data = await res.json()
        if (data.success) {
          setTlfDemoMarkdown(data.markdown)
        } else {
          throw new Error(data.message || 'TLF Demo generation failed')
        }
      }
    } catch (err: any) {
      setTlfDemoError(err.message || 'TLF Demo generation failed')
    } finally {
      setTlfDemoLoading(false)
    }
  }

  // Generate TLF Shells directly from protocol (no SAP needed) — OLD deterministic system
  const handleGenerateTlfShells = async (format: 'markdown' | 'docx' = 'markdown') => {
    if (mode === 'file' && !file) return
    if (mode === 'text' && !textInput.trim()) return

    setTlfLoading(true)
    setTlfError(null)
    setTlfMarkdown(null)

    try {
      // Build skills query param if skills are selected
      const skillsParam = selectedSkills.size > 0 ? `&skills=${Array.from(selectedSkills).join(',')}` : ''

      if (mode === 'file' && file) {
        const formData = new FormData()
        formData.append('file', file)

        const res = await fetch(`${API_URL}/generate-tlf-shells-direct?format=${format}${skillsParam}`, {
          method: 'POST',
          body: formData,
        })

        if (!res.ok) {
          const data = await res.json()
          throw new Error(data.detail || 'TLF shell generation failed')
        }

        if (format === 'docx') {
          const blob = await res.blob()
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = `TLF_Shells_${file.name.replace(/\.[^/.]+$/, '')}.docx`
          a.click()
          URL.revokeObjectURL(url)
        } else {
          const data = await res.json()
          if (data.success) {
            setTlfMarkdown(data.markdown)
          } else {
            throw new Error(data.message || 'TLF shell generation failed')
          }
        }
      } else if (mode === 'text' && textInput.trim()) {
        // For text mode, create a text file blob and send as file upload
        const blob = new Blob([textInput], { type: 'text/plain' })
        const textFile = new File([blob], 'protocol.txt', { type: 'text/plain' })
        const formData = new FormData()
        formData.append('file', textFile)

        const res = await fetch(`${API_URL}/generate-tlf-shells-direct?format=${format}${skillsParam}`, {
          method: 'POST',
          body: formData,
        })

        if (!res.ok) {
          const data = await res.json()
          throw new Error(data.detail || 'TLF shell generation failed')
        }

        if (format === 'docx') {
          const blob = await res.blob()
          const url = URL.createObjectURL(blob)
          const a = document.createElement('a')
          a.href = url
          a.download = 'TLF_Shells_protocol.docx'
          a.click()
          URL.revokeObjectURL(url)
        } else {
          const data = await res.json()
          if (data.success) {
            setTlfMarkdown(data.markdown)
          } else {
            throw new Error(data.message || 'TLF shell generation failed')
          }
        }
      }
    } catch (err: any) {
      setTlfError(err.message || 'TLF shell generation failed')
    } finally {
      setTlfLoading(false)
    }
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

        {/* Action Buttons */}
        <div className="flex gap-3">
          {/* Generate SAP Button */}
          <button
            type="submit"
            disabled={loading || tlfLoading || (mode === 'file' && !file) || (mode === 'text' && !textInput.trim())}
            className={`flex-1 py-3 px-4 rounded-xl font-medium text-white transition-colors ${
              loading || tlfLoading
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
                Generating SAP...
              </span>
            ) : (
              'Generate SAP'
            )}
          </button>

          {/* Generate TLF Shells Button (old deterministic) */}
          <button
            type="button"
            onClick={handleLoadSkillsPreview}
            disabled={loading || tlfLoading || tlfLlmLoading || skillsLoading || (mode === 'file' && !file) || (mode === 'text' && !textInput.trim())}
            className={`flex-1 py-3 px-4 rounded-xl font-medium text-white transition-colors ${
              loading || tlfLoading || tlfLlmLoading || skillsLoading
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-emerald-600 hover:bg-emerald-700'
            }`}
          >
            {skillsLoading ? (
              <span className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Analyzing Protocol...
              </span>
            ) : (
              'TLF Shells (Rules)'
            )}
          </button>

          {/* Generate TLF Shells LLM Button (new system) */}
          <button
            type="button"
            onClick={() => handleGenerateTlfLlm('markdown')}
            disabled={loading || tlfLoading || tlfLlmLoading || (mode === 'file' && !file) || (mode === 'text' && !textInput.trim())}
            className={`flex-1 py-3 px-4 rounded-xl font-medium text-white transition-colors ${
              loading || tlfLoading || tlfLlmLoading
                ? 'bg-gray-400 cursor-not-allowed'
                : 'bg-violet-600 hover:bg-violet-700'
            }`}
          >
            {tlfLlmLoading ? (
              <span className="flex items-center justify-center">
                <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Generating (LLM)...
              </span>
            ) : (
              'TLF Shells (LLM)'
            )}
          </button>

        </div>
      </form>

      {/* Demo TLF Section — requires protocol (above) + SAP file */}
      <div className="mt-6 bg-white rounded-xl shadow-sm border border-emerald-200 p-6">
        <h2 className="text-lg font-bold text-gray-900 mb-1">Demo TLF Generation</h2>
        <p className="text-sm text-gray-500 mb-4">
          Upload the generated SAP (.docx) below. The protocol file above provides clinical context.
          Generates 4 items: 2 tables + 2 listings from the SAP&apos;s TLF index.
        </p>

        {/* SAP File Upload */}
        <div className="flex items-center gap-3 mb-4">
          <label className="text-sm font-medium text-gray-700 whitespace-nowrap">SAP File (.docx):</label>
          <input
            type="file"
            accept=".docx"
            onChange={(e) => {
              const f = e.target.files?.[0] || null
              if (f && !f.name.toLowerCase().endsWith('.docx')) {
                setTlfDemoError('SAP file must be a .docx file')
                setSapFile(null)
              } else {
                setTlfDemoError(null)
                setSapFile(f)
              }
            }}
            className="flex-1 text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-emerald-50 file:text-emerald-700 hover:file:bg-emerald-100"
          />
          {sapFile && (
            <span className="text-xs text-emerald-600 font-medium">{sapFile.name}</span>
          )}
        </div>

        {/* Generate Button */}
        <button
          type="button"
          onClick={() => handleGenerateTlfDemo('markdown')}
          disabled={loading || tlfLoading || tlfLlmLoading || tlfDemoLoading || !sapFile || (mode === 'file' && !file) || (mode === 'text' && !textInput.trim())}
          className={`w-full py-3 px-4 rounded-xl font-medium text-white transition-colors ${
            loading || tlfLoading || tlfLlmLoading || tlfDemoLoading || !sapFile || (mode === 'file' && !file) || (mode === 'text' && !textInput.trim())
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-emerald-600 hover:bg-emerald-700'
          }`}
        >
          {tlfDemoLoading ? (
            <span className="flex items-center justify-center">
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Generating Demo TLFs (2 API calls)...
            </span>
          ) : (
            'Generate Demo TLFs'
          )}
        </button>
      </div>

      {/* TLF Skills Selector */}
      {showSkillSelector && tlfSkills.length > 0 && (
        <div className="mt-6 bg-white rounded-xl shadow-sm border p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-bold text-gray-900">TLF Skills</h2>
              <p className="text-sm text-gray-500 mt-1">
                Select which sections to generate. {selectedSkills.size} of {tlfSkills.filter(s => s.has_content).length} skills selected.
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={toggleAllSkills}
                className="px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
              >
                {selectedSkills.size === tlfSkills.filter(s => s.has_content).length ? 'Deselect All' : 'Select All'}
              </button>
              <button
                onClick={() => { setShowSkillSelector(false); setTlfSkills([]) }}
                className="px-3 py-1.5 text-xs font-medium text-gray-400 hover:text-gray-600 transition-colors"
              >
                Close
              </button>
            </div>
          </div>

          {/* ICH Section Groups */}
          {['14.1', '14.2', '14.3', '14.4', '16.2', 'varies'].map(section => {
            const sectionSkills = tlfSkills.filter(s => s.ich_section === section)
            if (sectionSkills.length === 0) return null
            const sectionLabel: Record<string, string> = {
              '14.1': 'Demographics & Disposition',
              '14.2': 'Efficacy',
              '14.3': 'Safety',
              '14.4': 'PK & Immunogenicity',
              '16.2': 'Listings',
              'varies': 'Figures',
            }
            return (
              <div key={section} className="mb-4">
                <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                  Section {section} — {sectionLabel[section] || section}
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {sectionSkills.map(skill => (
                    <label
                      key={skill.id}
                      className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                        !skill.has_content
                          ? 'opacity-40 cursor-not-allowed bg-gray-50 border-gray-200'
                          : selectedSkills.has(skill.id)
                          ? 'bg-emerald-50 border-emerald-300'
                          : 'bg-white border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedSkills.has(skill.id)}
                        onChange={() => toggleSkill(skill.id)}
                        disabled={!skill.has_content}
                        className="mt-0.5 h-4 w-4 text-emerald-600 rounded border-gray-300 focus:ring-emerald-500"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-gray-900">{skill.name}</span>
                          <span className="text-xs text-gray-400 ml-2 whitespace-nowrap">
                            {skill.total_count} {skill.total_count === 1 ? 'output' : 'outputs'}
                          </span>
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5 truncate">{skill.description}</p>
                        {skill.has_content && (
                          <div className="flex gap-2 mt-1">
                            {skill.table_count > 0 && <span className="text-xs text-blue-600">{skill.table_count}T</span>}
                            {skill.figure_count > 0 && <span className="text-xs text-purple-600">{skill.figure_count}F</span>}
                            {skill.listing_count > 0 && <span className="text-xs text-amber-600">{skill.listing_count}L</span>}
                          </div>
                        )}
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            )
          })}

          {/* Generate Button */}
          <div className="flex gap-2 mt-4 pt-4 border-t">
            <button
              onClick={() => handleGenerateTlfShells('markdown')}
              disabled={tlfLoading || selectedSkills.size === 0}
              className={`flex-1 py-2.5 px-4 rounded-lg font-medium text-white transition-colors ${
                tlfLoading || selectedSkills.size === 0
                  ? 'bg-gray-400 cursor-not-allowed'
                  : 'bg-emerald-600 hover:bg-emerald-700'
              }`}
            >
              {tlfLoading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Generating...
                </span>
              ) : (
                `Generate ${selectedSkills.size} Skill${selectedSkills.size !== 1 ? 's' : ''} (Markdown)`
              )}
            </button>
            <button
              onClick={() => handleGenerateTlfShells('docx')}
              disabled={tlfLoading || selectedSkills.size === 0}
              className={`py-2.5 px-4 rounded-lg font-medium transition-colors ${
                tlfLoading || selectedSkills.size === 0
                  ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                  : 'bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100'
              }`}
            >
              .docx
            </button>
          </div>
        </div>
      )}

      {/* TLF Shell Error */}
      {tlfError && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-700">{tlfError}</p>
        </div>
      )}

      {/* TLF Shell Results */}
      {tlfMarkdown && (
        <div className="mt-6 bg-white rounded-xl shadow-sm border p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-gray-900">TLF Shell Specifications</h2>
            <div className="flex gap-2">
              <button
                onClick={() => handleGenerateTlfShells('docx')}
                disabled={tlfLoading}
                className="px-4 py-2 text-sm font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition-colors"
              >
                Download .docx
              </button>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(tlfMarkdown)
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-50 border border-gray-200 rounded-lg hover:bg-gray-100 transition-colors"
              >
                Copy Markdown
              </button>
            </div>
          </div>
          <div className="markdown-body max-w-none overflow-x-auto text-sm">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {tlfMarkdown}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {/* TLF LLM Error */}
      {tlfLlmError && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-700">{tlfLlmError}</p>
        </div>
      )}

      {/* TLF LLM Results */}
      {tlfLlmMarkdown && (
        <div className="mt-6 bg-white rounded-xl shadow-sm border border-violet-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl font-bold text-gray-900">TLF Shell Specifications (LLM-Driven)</h2>
              <p className="text-sm text-violet-600 mt-1">Generated via domain-by-domain LLM reasoning with example matching</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleGenerateTlfLlm('docx')}
                disabled={tlfLlmLoading}
                className="px-4 py-2 text-sm font-medium text-violet-700 bg-violet-50 border border-violet-200 rounded-lg hover:bg-violet-100 transition-colors"
              >
                Download .docx
              </button>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(tlfLlmMarkdown)
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-50 border border-gray-200 rounded-lg hover:bg-gray-100 transition-colors"
              >
                Copy Markdown
              </button>
            </div>
          </div>
          <div className="markdown-body max-w-none overflow-x-auto text-sm">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {tlfLlmMarkdown}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {/* TLF Demo Error */}
      {tlfDemoError && (
        <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-700">{tlfDemoError}</p>
        </div>
      )}

      {/* TLF Demo Results */}
      {tlfDemoMarkdown && (
        <div className="mt-6 bg-white rounded-xl shadow-sm border border-emerald-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Demo TLF Shells (from SAP Index)</h2>
              <p className="text-sm text-emerald-600 mt-1">4 items: 2 tables + 2 listings — parsed from SAP TLF index</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => handleGenerateTlfDemo('docx')}
                disabled={tlfDemoLoading}
                className="px-4 py-2 text-sm font-medium text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg hover:bg-emerald-100 transition-colors"
              >
                Download .docx
              </button>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(tlfDemoMarkdown)
                }}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-50 border border-gray-200 rounded-lg hover:bg-gray-100 transition-colors"
              >
                Copy Markdown
              </button>
            </div>
          </div>
          <div className="markdown-body max-w-none overflow-x-auto text-sm">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {tlfDemoMarkdown}
            </ReactMarkdown>
          </div>
        </div>
      )}

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

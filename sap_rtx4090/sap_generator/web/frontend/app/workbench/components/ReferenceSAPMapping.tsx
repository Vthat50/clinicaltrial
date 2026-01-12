'use client'

import { useState, useEffect } from 'react'
import {
  Upload,
  FileText,
  Check,
  X,
  Loader2,
  Link2,
  AlertCircle,
  ChevronDown,
  Save,
  RefreshCw,
} from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ReferenceSection {
  id: string
  title: string
  content_preview: string
}

interface SectionMapping {
  [generatedSectionId: string]: string | null  // maps to reference section id or null
}

interface ReferenceSAPMappingProps {
  workspaceId: string
  generatedSections: { id: string; name: string; display_name: string }[]
  onMappingComplete?: () => void
}

export default function ReferenceSAPMapping({
  workspaceId,
  generatedSections,
  onMappingComplete,
}: ReferenceSAPMappingProps) {
  const [uploading, setUploading] = useState(false)
  const [referenceSections, setReferenceSections] = useState<ReferenceSection[]>([])
  const [mapping, setMapping] = useState<SectionMapping>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [referenceFilename, setReferenceFilename] = useState<string | null>(null)
  const [hasReference, setHasReference] = useState(false)

  // Fetch existing reference SAP status on mount
  useEffect(() => {
    fetchReferenceStatus()
  }, [workspaceId])

  const fetchReferenceStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/workbench/${workspaceId}/reference-sap/status`)
      if (res.ok) {
        const data = await res.json()
        setHasReference(data.has_reference)
        setReferenceFilename(data.filename)
        if (data.sections) {
          setReferenceSections(data.sections)
        }
        if (data.mapping) {
          setMapping(data.mapping)
        }
      }
    } catch (e) {
      console.error('Failed to fetch reference status:', e)
    }
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    setError(null)

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch(`${API_URL}/workbench/${workspaceId}/reference-sap/upload`, {
        method: 'POST',
        body: formData,
      })

      if (res.ok) {
        const data = await res.json()
        setHasReference(true)
        setReferenceFilename(file.name)
        // Fetch the parsed sections
        await fetchReferenceStatus()
      } else {
        const err = await res.json()
        setError(err.detail || 'Failed to upload reference SAP')
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setUploading(false)
    }
  }

  const handleMappingChange = (generatedSectionId: string, referenceSectionId: string | null) => {
    setMapping((prev) => ({
      ...prev,
      [generatedSectionId]: referenceSectionId,
    }))
  }

  const handleSaveMapping = async () => {
    setSaving(true)
    setError(null)

    try {
      const res = await fetch(`${API_URL}/workbench/${workspaceId}/reference-sap/mapping`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mapping }),
      })

      if (res.ok) {
        onMappingComplete?.()
      } else {
        const err = await res.json()
        setError(err.detail || 'Failed to save mapping')
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  const getMappedCount = () => {
    return Object.values(mapping).filter((v) => v !== null && v !== '').length
  }

  return (
    <div className="bg-white rounded-lg border p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-medium text-gray-900 flex items-center gap-2">
          <Link2 className="w-5 h-5 text-indigo-600" />
          Reference SAP Mapping
        </h3>
        {hasReference && (
          <span className="text-sm text-green-600 flex items-center gap-1">
            <Check className="w-4 h-4" />
            {referenceFilename}
          </span>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md text-sm flex items-start gap-2">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          {error}
        </div>
      )}

      {/* Upload Section */}
      {!hasReference ? (
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
          <Upload className="w-10 h-10 mx-auto text-gray-400 mb-3" />
          <p className="text-gray-600 mb-3">Upload a reference SAP to compare against</p>
          <label className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-md cursor-pointer hover:bg-indigo-700 transition-colors">
            {uploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Uploading...
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                Select PDF or TXT
              </>
            )}
            <input
              type="file"
              accept=".pdf,.txt,.docx"
              onChange={handleUpload}
              disabled={uploading}
              className="hidden"
            />
          </label>
        </div>
      ) : (
        <>
          {/* Mapping Table */}
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm text-gray-600">
                Map each generated section to its corresponding reference section:
              </p>
              <span className="text-sm text-gray-500">
                {getMappedCount()} / {generatedSections.length} mapped
              </span>
            </div>

            <div className="border rounded-lg overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Generated Section
                    </th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                      Reference Section
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {generatedSections.map((section) => (
                    <tr key={section.id} className="hover:bg-gray-50">
                      <td className="px-4 py-2">
                        <div className="flex items-center gap-2">
                          <FileText className="w-4 h-4 text-gray-400" />
                          <span className="text-sm font-medium text-gray-900">
                            {section.display_name || section.name}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-2">
                        <div className="relative">
                          <select
                            value={mapping[section.id] || ''}
                            onChange={(e) =>
                              handleMappingChange(
                                section.id,
                                e.target.value || null
                              )
                            }
                            className="w-full appearance-none bg-white border border-gray-300 rounded-md py-1.5 pl-3 pr-8 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                          >
                            <option value="">-- No match --</option>
                            {referenceSections.map((ref) => (
                              <option key={ref.id} value={ref.id}>
                                {ref.id} - {ref.title}
                              </option>
                            ))}
                          </select>
                          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between">
            <label className="inline-flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 cursor-pointer">
              <RefreshCw className="w-4 h-4" />
              Upload Different File
              <input
                type="file"
                accept=".pdf,.txt,.docx"
                onChange={handleUpload}
                disabled={uploading}
                className="hidden"
              />
            </label>

            <button
              onClick={handleSaveMapping}
              disabled={saving || getMappedCount() === 0}
              className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  Save Mapping
                </>
              )}
            </button>
          </div>
        </>
      )}

      {/* Help text */}
      <p className="mt-4 text-xs text-gray-500">
        Manually map each section to ensure accurate comparison. Sections that don't have a match in
        the reference SAP can be left as "No match".
      </p>
    </div>
  )
}

'use client'

import { useState, useMemo, useCallback } from 'react'
import {
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  Upload,
  X,
  Loader2,
  FileText,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface AccuracyHighlightViewProps {
  workspaceId: string
  sectionContent: string
  referenceContent?: string | null
  comparisonResult: any
  onClose: () => void
  onUploadReference: () => void
  onRefreshComparison: () => void
}

export default function AccuracyHighlightView({
  workspaceId,
  sectionContent,
  referenceContent,
  comparisonResult,
  onClose,
  onUploadReference,
  onRefreshComparison,
}: AccuracyHighlightViewProps) {
  const [activeTab, setActiveTab] = useState<'highlighted' | 'sidebyside' | 'details'>('highlighted')
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [showDetails, setShowDetails] = useState<Record<string, boolean>>({})

  const hasReference = comparisonResult?.has_reference
  const sectionFound = comparisonResult?.section_found
  const comparison = comparisonResult?.comparison

  // Handle direct file upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) {
      setUploadError('No file selected')
      return
    }

    console.log('[AccuracyHighlightView] Uploading file:', file.name, 'to workspace:', workspaceId)

    setUploading(true)
    setUploadError(null)

    const formData = new FormData()
    formData.append('file', file)

    const uploadUrl = `${API_URL}/workbench/${workspaceId}/reference-sap`
    console.log('[AccuracyHighlightView] Upload URL:', uploadUrl)

    try {
      const res = await fetch(uploadUrl, {
        method: 'POST',
        body: formData,
      })

      console.log('[AccuracyHighlightView] Response status:', res.status)

      if (res.ok) {
        // Open full mapping UI after upload
        onUploadReference()
      } else {
        const err = await res.json()
        console.error('[AccuracyHighlightView] Upload error:', err)
        setUploadError(err.detail || `Upload failed: ${res.status} ${res.statusText}`)
      }
    } catch (e: any) {
      console.error('[AccuracyHighlightView] Fetch error:', e)
      setUploadError(`Network error: ${e.message}`)
    } finally {
      setUploading(false)
    }
  }

  // Create highlighted content by marking correct/incorrect/missing elements
  const highlightedContent = useMemo(() => {
    if (!comparison || !sectionContent) return null

    let content = sectionContent

    // We'll create a component that renders the content with highlights
    const highlights: Array<{
      type: 'correct' | 'incorrect' | 'missing' | 'extra'
      text: string
      details?: any
    }> = []

    // Collect correct content
    comparison.correct_content?.forEach((item: string) => {
      highlights.push({ type: 'correct', text: item })
    })

    // Collect incorrect content
    comparison.incorrect_content?.forEach((item: any) => {
      highlights.push({
        type: 'incorrect',
        text: item.element,
        details: item,
      })
    })

    // Collect missing content
    comparison.missing_content?.forEach((item: any) => {
      highlights.push({
        type: 'missing',
        text: item.element,
        details: item,
      })
    })

    // Collect extra content
    comparison.extra_content?.forEach((item: any) => {
      highlights.push({
        type: 'extra',
        text: item.element,
        details: item,
      })
    })

    return highlights
  }, [comparison, sectionContent])

  // Helper function to escape regex special characters
  const escapeRegex = (str: string) => {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  }

  // Apply inline highlights to text content
  const applyHighlights = useCallback((
    content: string,
    highlightPhrases: Array<{ text: string; type: 'correct' | 'missing' | 'incorrect' | 'extra' }>
  ): React.ReactNode[] => {
    console.log('[applyHighlights] Called with', content?.length, 'chars,', highlightPhrases.length, 'phrases')
    if (!highlightPhrases.length) {
      console.log('[applyHighlights] No phrases to highlight, returning plain text')
      // Return content split by lines for basic rendering
      return content.split('\n').map((line, i) => (
        <span key={i}>
          {line}
          {i < content.split('\n').length - 1 && <br />}
        </span>
      ))
    }

    // Sort phrases by length (longest first) to avoid partial matches
    const sortedPhrases = [...highlightPhrases].sort((a, b) => b.text.length - a.text.length)

    // Build a map of positions to highlight
    interface Highlight {
      start: number
      end: number
      type: 'correct' | 'missing' | 'incorrect' | 'extra'
      text: string
    }
    const highlights: Highlight[] = []

    sortedPhrases.forEach(({ text, type }) => {
      if (!text || text.length < 3) return // Skip very short phrases

      try {
        // Try exact match first, then case-insensitive
        const escapedText = escapeRegex(text)
        const regex = new RegExp(escapedText, 'gi')
        let match
        while ((match = regex.exec(content)) !== null) {
          // Check if this position overlaps with existing highlight
          const overlaps = highlights.some(
            h => (match!.index >= h.start && match!.index < h.end) ||
                 (match!.index + text.length > h.start && match!.index + text.length <= h.end)
          )
          if (!overlaps) {
            highlights.push({
              start: match.index,
              end: match.index + match[0].length,
              type,
              text: match[0]
            })
          }
        }
      } catch (e) {
        // Invalid regex, skip this phrase
      }
    })

    // Sort highlights by position
    highlights.sort((a, b) => a.start - b.start)

    // Build the result with highlights
    const result: React.ReactNode[] = []
    let lastIndex = 0

    highlights.forEach((h, i) => {
      // Add text before this highlight
      if (h.start > lastIndex) {
        const beforeText = content.slice(lastIndex, h.start)
        result.push(
          <span key={`text-${i}`}>
            {beforeText.split('\n').map((line, j, arr) => (
              <span key={j}>
                {line}
                {j < arr.length - 1 && <br />}
              </span>
            ))}
          </span>
        )
      }

      // Add highlighted text
      const bgColor = {
        correct: 'bg-green-200 border-green-400',
        missing: 'bg-red-200 border-red-400',
        incorrect: 'bg-orange-200 border-orange-400',
        extra: 'bg-blue-200 border-blue-400',
      }[h.type]

      result.push(
        <mark
          key={`highlight-${i}`}
          className={`${bgColor} border-b-2 px-0.5 rounded-sm`}
          title={`${h.type}: ${h.text}`}
        >
          {h.text}
        </mark>
      )

      lastIndex = h.end
    })

    // Add remaining text
    if (lastIndex < content.length) {
      const remainingText = content.slice(lastIndex)
      result.push(
        <span key="text-end">
          {remainingText.split('\n').map((line, j, arr) => (
            <span key={j}>
              {line}
              {j < arr.length - 1 && <br />}
            </span>
          ))}
        </span>
      )
    }

    return result.length > 0 ? result : [<span key="empty">{content}</span>]
  }, [])

  // Find common phrases between reference and generated content (direct text matching)
  const findCommonPhrases = useCallback((refContent: string, genContent: string, minWords: number = 3): string[] => {
    if (!refContent || !genContent) return []

    // Normalize text - lowercase, remove extra whitespace
    const normalize = (text: string) => text.toLowerCase().replace(/\s+/g, ' ').trim()
    const refNorm = normalize(refContent)
    const genNorm = normalize(genContent)

    // Extract sentences and phrases
    const refSentences = refContent.split(/[.!?\n]+/).map(s => s.trim()).filter(s => s.length > 10)
    const genSentences = genContent.split(/[.!?\n]+/).map(s => s.trim()).filter(s => s.length > 10)

    const commonPhrases: string[] = []

    // Find common sentences (fuzzy match)
    refSentences.forEach(refSent => {
      const refSentNorm = normalize(refSent)
      genSentences.forEach(genSent => {
        const genSentNorm = normalize(genSent)
        // Check if sentences are similar (one contains most of the other)
        if (refSentNorm.length > 20 && genSentNorm.length > 20) {
          if (refSentNorm.includes(genSentNorm) || genSentNorm.includes(refSentNorm)) {
            commonPhrases.push(refSent.length < genSent.length ? refSent : genSent)
          }
        }
      })
    })

    // Also find common n-grams (phrases of N words)
    const extractNgrams = (text: string, n: number): string[] => {
      const words = text.split(/\s+/)
      const ngrams: string[] = []
      for (let i = 0; i <= words.length - n; i++) {
        ngrams.push(words.slice(i, i + n).join(' '))
      }
      return ngrams
    }

    // Find common 4-8 word phrases
    for (let n = 8; n >= minWords; n--) {
      const refNgrams = new Set(extractNgrams(refNorm, n))
      const genNgrams = extractNgrams(genNorm, n)
      genNgrams.forEach(ngram => {
        if (refNgrams.has(ngram) && ngram.length > 15) {
          // Find original case version from source
          const regex = new RegExp(ngram.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i')
          const match = refContent.match(regex)
          if (match) {
            commonPhrases.push(match[0])
          }
        }
      })
    }

    // Dedupe and return
    return [...new Set(commonPhrases)].slice(0, 100) // Limit to avoid performance issues
  }, [])

  // Common phrases between reference and generated (direct text match)
  const commonPhrases = useMemo(() => {
    if (!referenceContent || !sectionContent) {
      console.log('[Highlight] No content for phrase matching:', { hasRef: !!referenceContent, hasGen: !!sectionContent })
      return []
    }
    const phrases = findCommonPhrases(referenceContent, sectionContent, 3)
    console.log('[Highlight] Found common phrases:', phrases.length, phrases.slice(0, 5))
    return phrases
  }, [referenceContent, sectionContent, findCommonPhrases])

  // Build highlight phrases for reference panel (correct + missing + common phrases)
  const referenceHighlights = useMemo(() => {
    const phrases: Array<{ text: string; type: 'correct' | 'missing' | 'incorrect' | 'extra' }> = []

    // Add common phrases found via direct text matching (most important - highlight in green)
    // This works even without comparison data!
    commonPhrases.forEach((phrase: string) => {
      phrases.push({ text: phrase, type: 'correct' })
    })
    console.log('[Highlight] Reference highlights from direct matching:', commonPhrases.length)

    if (!comparison) {
      console.log('[Highlight] No comparison data, using only direct text matching')
      return phrases
    }

    // Correct content from Claude's analysis (found in both)
    comparison.correct_content?.forEach((item: string) => {
      phrases.push({ text: item, type: 'correct' })
    })

    // Missing content (in reference, not in generated)
    comparison.missing_content?.forEach((item: any) => {
      if (item.original_text) phrases.push({ text: item.original_text, type: 'missing' })
      else if (item.element) phrases.push({ text: item.element, type: 'missing' })
    })

    // Incorrect content (different between ref and generated) - show original in reference
    comparison.incorrect_content?.forEach((item: any) => {
      if (item.original) phrases.push({ text: item.original, type: 'incorrect' })
    })

    return phrases
  }, [comparison, commonPhrases])

  // Build highlight phrases for generated panel (correct + extra + incorrect + common phrases)
  const generatedHighlights = useMemo(() => {
    const phrases: Array<{ text: string; type: 'correct' | 'missing' | 'incorrect' | 'extra' }> = []

    // Add common phrases found via direct text matching (most important - highlight in green)
    // This works even without comparison data!
    commonPhrases.forEach((phrase: string) => {
      phrases.push({ text: phrase, type: 'correct' })
    })
    console.log('[Highlight] Generated highlights from direct matching:', commonPhrases.length)

    if (!comparison) {
      console.log('[Highlight] No comparison data for generated, using only direct text matching')
      return phrases
    }

    // Correct content from Claude's analysis (found in both)
    comparison.correct_content?.forEach((item: string) => {
      phrases.push({ text: item, type: 'correct' })
    })

    // Extra content (in generated, not in reference)
    comparison.extra_content?.forEach((item: any) => {
      if (item.element) phrases.push({ text: item.element, type: 'extra' })
    })

    // Incorrect content - show generated version
    comparison.incorrect_content?.forEach((item: any) => {
      if (item.generated) phrases.push({ text: item.generated, type: 'incorrect' })
    })

    console.log('[Highlight] Generated highlights total:', phrases.length)
    return phrases
  }, [comparison, commonPhrases])

  const toggleDetails = (key: string) => {
    setShowDetails((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const accuracyPercentage = comparison?.accuracy_percentage ?? 0
  const accuracyColor =
    accuracyPercentage >= 80
      ? 'text-green-600 bg-green-100'
      : accuracyPercentage >= 60
      ? 'text-yellow-600 bg-yellow-100'
      : 'text-red-600 bg-red-100'

  // No reference uploaded
  if (!hasReference) {
    return (
      <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Check Accuracy</h2>
            <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>

          <div className="text-center py-8">
            <FileText className="w-16 h-16 mx-auto text-gray-300 mb-4" />
            <h3 className="text-lg font-medium text-gray-700 mb-2">No Reference SAP</h3>
            <p className="text-gray-500 mb-6">
              Upload a reference SAP document to compare against and check accuracy.
            </p>

            {uploadError && (
              <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-md text-sm">
                {uploadError}
              </div>
            )}

            <label className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-lg cursor-pointer hover:bg-indigo-700 transition-colors">
              {uploading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="w-5 h-5" />
                  Upload Reference SAP
                </>
              )}
              <input
                type="file"
                accept=".pdf,.txt,.docx"
                onChange={handleFileUpload}
                disabled={uploading}
                className="hidden"
              />
            </label>
            <p className="mt-3 text-xs text-gray-400">Supports PDF, TXT, and DOCX files</p>
          </div>
        </div>
      </div>
    )
  }

  // Reference uploaded but section not mapped
  if (!sectionFound) {
    return (
      <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Section Not Mapped</h2>
            <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>

          <div className="text-center py-6">
            <AlertTriangle className="w-12 h-12 mx-auto text-yellow-500 mb-4" />
            <p className="text-gray-600 mb-4">{comparisonResult.message}</p>
            <button
              onClick={onUploadReference}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              Configure Section Mapping
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Full accuracy view with highlights
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-6xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b flex items-center justify-between shrink-0">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-semibold text-gray-900">Accuracy Analysis</h2>
            <span className={`px-3 py-1 rounded-full text-sm font-bold ${accuracyColor}`}>
              {accuracyPercentage}% Match
            </span>
            {comparisonResult.reference_section_id && (
              <span className="text-sm text-gray-500">
                vs. {comparisonResult.reference_section_id}
              </span>
            )}
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Tabs */}
        <div className="px-6 py-2 border-b flex gap-4 shrink-0">
          <button
            onClick={() => setActiveTab('highlighted')}
            className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
              activeTab === 'highlighted'
                ? 'bg-indigo-100 text-indigo-700'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            Highlighted View
          </button>
          <button
            onClick={() => setActiveTab('sidebyside')}
            className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
              activeTab === 'sidebyside'
                ? 'bg-indigo-100 text-indigo-700'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            Side by Side
          </button>
          <button
            onClick={() => setActiveTab('details')}
            className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
              activeTab === 'details'
                ? 'bg-indigo-100 text-indigo-700'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            Detailed Report
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'highlighted' && (
            <div className="h-full flex">
              {/* Legend */}
              <div className="w-64 border-r p-4 overflow-y-auto bg-gray-50">
                <h3 className="text-sm font-medium text-gray-700 mb-3">Legend</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 bg-green-200 border border-green-400 rounded"></span>
                    <span>Correct ({comparison?.correct_content?.length || 0})</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 bg-red-200 border border-red-400 rounded"></span>
                    <span>Missing ({comparison?.missing_content?.length || 0})</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 bg-orange-200 border border-orange-400 rounded"></span>
                    <span>Incorrect ({comparison?.incorrect_content?.length || 0})</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-4 h-4 bg-blue-200 border border-blue-400 rounded"></span>
                    <span>Extra ({comparison?.extra_content?.length || 0})</span>
                  </div>
                </div>

                {/* Summary */}
                {comparison?.summary && (
                  <div className="mt-6">
                    <h3 className="text-sm font-medium text-gray-700 mb-2">Summary</h3>
                    <p className="text-sm text-gray-600">{comparison.summary}</p>
                  </div>
                )}

                {/* Quick Actions */}
                <div className="mt-6 space-y-2">
                  <button
                    onClick={onRefreshComparison}
                    className="w-full px-3 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
                  >
                    Re-check Accuracy
                  </button>
                  <button
                    onClick={onUploadReference}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-100"
                  >
                    Change Reference
                  </button>
                </div>
              </div>

              {/* Highlighted Content */}
              <div className="flex-1 overflow-y-auto p-6">
                <div className="prose prose-sm max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {sectionContent}
                  </ReactMarkdown>
                </div>

                {/* Highlight Annotations */}
                <div className="mt-8 border-t pt-6">
                  <h3 className="text-sm font-medium text-gray-700 mb-4">Analysis Details</h3>

                  {/* Correct Items */}
                  {comparison?.correct_content?.length > 0 && (
                    <div className="mb-6">
                      <h4 className="text-sm font-medium text-green-700 flex items-center gap-2 mb-2">
                        <CheckCircle className="w-4 h-4" />
                        Correct Elements
                      </h4>
                      <div className="flex flex-wrap gap-2">
                        {comparison.correct_content.map((item: string, i: number) => (
                          <span
                            key={i}
                            className="px-3 py-1.5 bg-green-100 border border-green-300 text-green-800 rounded-lg text-sm"
                          >
                            {item}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Missing Items */}
                  {comparison?.missing_content?.length > 0 && (
                    <div className="mb-6">
                      <h4 className="text-sm font-medium text-red-700 flex items-center gap-2 mb-2">
                        <AlertCircle className="w-4 h-4" />
                        Missing Elements
                      </h4>
                      <div className="space-y-2">
                        {comparison.missing_content.map((item: any, i: number) => (
                          <div
                            key={i}
                            className="bg-red-50 border border-red-200 rounded-lg overflow-hidden"
                          >
                            <button
                              onClick={() => toggleDetails(`missing-${i}`)}
                              className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-red-100"
                            >
                              <span className="font-medium text-red-800">{item.element}</span>
                              <div className="flex items-center gap-2">
                                {item.importance && (
                                  <span
                                    className={`px-2 py-0.5 text-xs rounded ${
                                      item.importance === 'critical'
                                        ? 'bg-red-600 text-white'
                                        : item.importance === 'important'
                                        ? 'bg-yellow-500 text-white'
                                        : 'bg-gray-400 text-white'
                                    }`}
                                  >
                                    {item.importance}
                                  </span>
                                )}
                                {showDetails[`missing-${i}`] ? (
                                  <ChevronUp className="w-4 h-4 text-red-600" />
                                ) : (
                                  <ChevronDown className="w-4 h-4 text-red-600" />
                                )}
                              </div>
                            </button>
                            {showDetails[`missing-${i}`] && (
                              <div className="px-4 py-3 border-t border-red-200 bg-red-25 text-sm">
                                {item.original_text && (
                                  <div className="mb-2">
                                    <span className="text-gray-500">From reference: </span>
                                    <span className="italic text-red-700">"{item.original_text}"</span>
                                  </div>
                                )}
                                {item.suggestion && (
                                  <div className="text-gray-700">
                                    <span className="font-medium">Suggestion: </span>
                                    {item.suggestion}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Incorrect Items */}
                  {comparison?.incorrect_content?.length > 0 && (
                    <div className="mb-6">
                      <h4 className="text-sm font-medium text-orange-700 flex items-center gap-2 mb-2">
                        <AlertTriangle className="w-4 h-4" />
                        Incorrect Elements
                      </h4>
                      <div className="space-y-2">
                        {comparison.incorrect_content.map((item: any, i: number) => (
                          <div
                            key={i}
                            className="bg-orange-50 border border-orange-200 rounded-lg overflow-hidden"
                          >
                            <button
                              onClick={() => toggleDetails(`incorrect-${i}`)}
                              className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-orange-100"
                            >
                              <span className="font-medium text-orange-800">{item.element}</span>
                              {showDetails[`incorrect-${i}`] ? (
                                <ChevronUp className="w-4 h-4 text-orange-600" />
                              ) : (
                                <ChevronDown className="w-4 h-4 text-orange-600" />
                              )}
                            </button>
                            {showDetails[`incorrect-${i}`] && (
                              <div className="px-4 py-3 border-t border-orange-200 text-sm space-y-2">
                                {item.original && (
                                  <div className="p-2 bg-green-50 border border-green-200 rounded">
                                    <span className="text-green-700 font-medium">Should be: </span>
                                    <span className="text-green-800">{item.original}</span>
                                  </div>
                                )}
                                {item.generated && (
                                  <div className="p-2 bg-red-50 border border-red-200 rounded">
                                    <span className="text-red-700 font-medium">Currently: </span>
                                    <span className="text-red-800">{item.generated}</span>
                                  </div>
                                )}
                                {item.suggestion && (
                                  <div className="text-gray-700">
                                    <span className="font-medium">Fix: </span>
                                    {item.suggestion}
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Extra Items */}
                  {comparison?.extra_content?.length > 0 && (
                    <div className="mb-6">
                      <h4 className="text-sm font-medium text-blue-700 flex items-center gap-2 mb-2">
                        <AlertCircle className="w-4 h-4" />
                        Extra Content (not in reference)
                      </h4>
                      <div className="space-y-2">
                        {comparison.extra_content.map((item: any, i: number) => (
                          <div
                            key={i}
                            className="bg-blue-50 border border-blue-200 rounded-lg p-3"
                          >
                            <div className="font-medium text-blue-800">{item.element}</div>
                            {item.assessment && (
                              <div className="text-sm text-blue-700 mt-1">{item.assessment}</div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'sidebyside' && (
            <div className="h-full flex flex-col">
              {/* Legend Bar */}
              <div className="px-4 py-2 bg-gray-50 border-b flex items-center gap-4 text-xs shrink-0">
                <span className="font-medium text-gray-600">Legend:</span>
                <div className="flex items-center gap-1">
                  <span className="w-3 h-3 bg-green-200 border border-green-400 rounded"></span>
                  <span className="text-gray-600">Matching</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-3 h-3 bg-red-200 border border-red-400 rounded"></span>
                  <span className="text-gray-600">Missing from generated</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-3 h-3 bg-orange-200 border border-orange-400 rounded"></span>
                  <span className="text-gray-600">Incorrect/Different</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-3 h-3 bg-blue-200 border border-blue-400 rounded"></span>
                  <span className="text-gray-600">Extra in generated</span>
                </div>
              </div>

              <div className="flex-1 flex overflow-hidden">
                {/* Reference Content */}
                <div className="w-1/2 border-r flex flex-col">
                  <div className="px-4 py-2 bg-amber-100 border-b text-sm font-medium text-amber-800 flex items-center justify-between">
                    <span>Reference SAP</span>
                    <span className="text-xs font-normal text-amber-600">
                      {referenceHighlights.length} elements to highlight
                    </span>
                  </div>
                  <div className="flex-1 overflow-y-auto p-4">
                    {referenceContent ? (
                      <div className="prose prose-sm max-w-none whitespace-pre-wrap font-sans text-sm leading-relaxed text-gray-800">
                        {applyHighlights(referenceContent, referenceHighlights)}
                      </div>
                    ) : (
                      <div className="text-center py-8 text-gray-500">
                        <FileText className="w-12 h-12 mx-auto text-gray-300 mb-2" />
                        <p>Reference content not available</p>
                        <button
                          onClick={onRefreshComparison}
                          className="mt-2 text-sm text-indigo-600 hover:underline"
                        >
                          Load reference
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                {/* Generated Content */}
                <div className="w-1/2 flex flex-col">
                  <div className="px-4 py-2 bg-blue-100 border-b text-sm font-medium text-blue-800 flex items-center justify-between">
                    <span>Generated SAP</span>
                    <span className="text-xs font-normal text-blue-600">
                      {generatedHighlights.length} elements to highlight
                    </span>
                  </div>
                  <div className="flex-1 overflow-y-auto p-4">
                    <div className="prose prose-sm max-w-none whitespace-pre-wrap font-sans text-sm leading-relaxed text-gray-800">
                      {applyHighlights(sectionContent, generatedHighlights)}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'details' && (
            <div className="h-full overflow-y-auto p-6">
              {/* Full Report */}
              <div className="max-w-4xl mx-auto space-y-6">
                {/* Summary */}
                {comparison?.summary && (
                  <div className="p-4 bg-gray-50 rounded-lg">
                    <h3 className="font-medium text-gray-900 mb-2">Summary</h3>
                    <p className="text-gray-700">{comparison.summary}</p>
                  </div>
                )}

                {/* Stats */}
                <div className="grid grid-cols-4 gap-4">
                  <div className="p-4 bg-green-50 rounded-lg text-center">
                    <div className="text-2xl font-bold text-green-700">
                      {comparison?.correct_content?.length || 0}
                    </div>
                    <div className="text-sm text-green-600">Correct</div>
                  </div>
                  <div className="p-4 bg-red-50 rounded-lg text-center">
                    <div className="text-2xl font-bold text-red-700">
                      {comparison?.missing_content?.length || 0}
                    </div>
                    <div className="text-sm text-red-600">Missing</div>
                  </div>
                  <div className="p-4 bg-orange-50 rounded-lg text-center">
                    <div className="text-2xl font-bold text-orange-700">
                      {comparison?.incorrect_content?.length || 0}
                    </div>
                    <div className="text-sm text-orange-600">Incorrect</div>
                  </div>
                  <div className="p-4 bg-blue-50 rounded-lg text-center">
                    <div className="text-2xl font-bold text-blue-700">
                      {comparison?.extra_content?.length || 0}
                    </div>
                    <div className="text-sm text-blue-600">Extra</div>
                  </div>
                </div>

                {/* Suggestions */}
                {comparison?.overall_suggestions?.length > 0 && (
                  <div className="p-4 bg-indigo-50 rounded-lg">
                    <h3 className="font-medium text-indigo-900 mb-3">Recommendations</h3>
                    <ul className="space-y-2">
                      {comparison.overall_suggestions.map((s: string, i: number) => (
                        <li key={i} className="flex items-start gap-2 text-indigo-800">
                          <span className="text-indigo-400 mt-1">•</span>
                          {s}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* All Details */}
                <div className="space-y-4">
                  {comparison?.missing_content?.map((item: any, i: number) => (
                    <div key={`m-${i}`} className="p-4 bg-red-50 border border-red-200 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <AlertCircle className="w-4 h-4 text-red-600" />
                        <span className="font-medium text-red-800">Missing: {item.element}</span>
                        {item.importance && (
                          <span
                            className={`px-2 py-0.5 text-xs rounded ${
                              item.importance === 'critical'
                                ? 'bg-red-600 text-white'
                                : item.importance === 'important'
                                ? 'bg-yellow-500 text-white'
                                : 'bg-gray-400 text-white'
                            }`}
                          >
                            {item.importance}
                          </span>
                        )}
                      </div>
                      {item.original_text && (
                        <p className="text-sm italic text-red-700 mb-2">"{item.original_text}"</p>
                      )}
                      {item.suggestion && (
                        <p className="text-sm text-gray-700">
                          <span className="font-medium">Suggestion:</span> {item.suggestion}
                        </p>
                      )}
                    </div>
                  ))}

                  {comparison?.incorrect_content?.map((item: any, i: number) => (
                    <div key={`i-${i}`} className="p-4 bg-orange-50 border border-orange-200 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <AlertTriangle className="w-4 h-4 text-orange-600" />
                        <span className="font-medium text-orange-800">Incorrect: {item.element}</span>
                      </div>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div className="p-2 bg-green-50 rounded">
                          <span className="text-green-700 font-medium">Expected:</span>{' '}
                          <span className="text-green-800">{item.original}</span>
                        </div>
                        <div className="p-2 bg-red-50 rounded">
                          <span className="text-red-700 font-medium">Got:</span>{' '}
                          <span className="text-red-800">{item.generated}</span>
                        </div>
                      </div>
                      {item.suggestion && (
                        <p className="text-sm text-gray-700 mt-2">
                          <span className="font-medium">Fix:</span> {item.suggestion}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

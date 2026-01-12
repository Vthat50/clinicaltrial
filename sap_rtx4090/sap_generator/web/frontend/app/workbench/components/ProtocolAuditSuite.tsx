'use client'

import { useEffect, useRef, useState, useMemo, useCallback } from 'react'
import {
  FileText,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Search,
  Loader2,
  AlertCircle,
  Maximize2,
  BookOpen,
  ChevronUp,
  ChevronDown,
} from 'lucide-react'
import { useWorkspaceStore } from '../stores/workspaceStore'
import FloatingFactDrawer from './FloatingFactDrawer'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface ProtocolAuditSuiteProps {
  workspaceId: string
  protocolTitle?: string
  studyId?: string
}

interface SearchMatch {
  index: number
  start: number
  end: number
}

export default function ProtocolAuditSuite({
  workspaceId,
  protocolTitle = 'Protocol Document',
  studyId,
}: ProtocolAuditSuiteProps) {
  const {
    scroll,
    setProtocolScroll,
    teleportTarget,
    clearTeleport,
    ui,
    toggleFactDrawer,
    closeFactDrawer,
    setViewMode,
  } = useWorkspaceStore()

  const containerRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const [zoom, setZoom] = useState(100)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchMatches, setSearchMatches] = useState<SearchMatch[]>([])
  const [currentMatchIndex, setCurrentMatchIndex] = useState(0)

  // Protocol content state
  const [protocolContent, setProtocolContent] = useState<string>('')
  const [protocolFilename, setProtocolFilename] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Fetch protocol content
  useEffect(() => {
    const fetchProtocol = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(`${API_URL}/workbench/${workspaceId}/protocol`)
        if (!res.ok) {
          throw new Error('Failed to fetch protocol')
        }
        const data = await res.json()
        setProtocolContent(data.content || '')
        setProtocolFilename(data.filename || 'protocol.txt')
      } catch (e: any) {
        setError(e.message)
      } finally {
        setLoading(false)
      }
    }

    if (workspaceId) {
      fetchProtocol()
    }
  }, [workspaceId])

  // Handle teleport - search for text when coming from fact drawer
  useEffect(() => {
    if (teleportTarget) {
      let searchTerm = ''

      // Priority 1: Use source_quote if available (the actual text from protocol)
      if (teleportTarget.sourceQuote && teleportTarget.sourceQuote.trim()) {
        const quote = teleportTarget.sourceQuote.trim()
        // Take first sentence or first 100 chars, whichever is shorter
        const firstSentence = quote.split('.')[0]
        searchTerm = firstSentence.length > 20 ? firstSentence : quote.slice(0, 100)
      }
      // Priority 2: Use searchText fallback (fact value/definition)
      else if (teleportTarget.searchText && teleportTarget.searchText.trim()) {
        searchTerm = teleportTarget.searchText.trim().slice(0, 100)
      }
      // Note: sourceSection (e.g., "Section 6.1") is NOT used for search
      // as it doesn't exist as literal text in the protocol

      if (searchTerm) {
        setSearchQuery(searchTerm)
      }
      clearTeleport()
    }
  }, [teleportTarget, clearTeleport])

  // Search functionality
  useEffect(() => {
    if (!searchQuery.trim() || !protocolContent) {
      setSearchMatches([])
      setCurrentMatchIndex(0)
      return
    }

    const query = searchQuery.toLowerCase()
    const content = protocolContent.toLowerCase()
    const matches: SearchMatch[] = []
    let startIndex = 0
    let matchIndex = 0

    while (true) {
      const index = content.indexOf(query, startIndex)
      if (index === -1) break
      matches.push({
        index: matchIndex++,
        start: index,
        end: index + query.length,
      })
      startIndex = index + 1
      if (matches.length > 1000) break // Limit matches
    }

    setSearchMatches(matches)
    setCurrentMatchIndex(0)

    // Scroll to first match
    if (matches.length > 0) {
      scrollToMatch(0, matches)
    }
  }, [searchQuery, protocolContent])

  const scrollToMatch = useCallback((index: number, matches: SearchMatch[]) => {
    if (!contentRef.current || !matches[index]) return

    const match = matches[index]
    // Find the element containing this match
    const highlightElements = contentRef.current.querySelectorAll('.search-highlight')
    const targetElement = highlightElements[index]

    if (targetElement) {
      targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [])

  const goToNextMatch = useCallback(() => {
    if (searchMatches.length === 0) return
    const nextIndex = (currentMatchIndex + 1) % searchMatches.length
    setCurrentMatchIndex(nextIndex)
    scrollToMatch(nextIndex, searchMatches)
  }, [currentMatchIndex, searchMatches, scrollToMatch])

  const goToPrevMatch = useCallback(() => {
    if (searchMatches.length === 0) return
    const prevIndex = (currentMatchIndex - 1 + searchMatches.length) % searchMatches.length
    setCurrentMatchIndex(prevIndex)
    scrollToMatch(prevIndex, searchMatches)
  }, [currentMatchIndex, searchMatches, scrollToMatch])

  // Restore scroll position on mount
  useEffect(() => {
    if (containerRef.current && !loading) {
      containerRef.current.scrollTop = scroll.protocol
    }
  }, [loading])

  // Save scroll position
  const handleScroll = () => {
    if (containerRef.current) {
      setProtocolScroll(containerRef.current.scrollTop)
    }
  }

  const handleZoomIn = () => setZoom((z) => Math.min(z + 25, 200))
  const handleZoomOut = () => setZoom((z) => Math.max(z - 25, 50))
  const handleZoomReset = () => setZoom(100)

  const handleSwitchToAuthoring = () => {
    setViewMode('sap-authoring')
  }

  // Render content with search highlighting
  const highlightedContent = useMemo(() => {
    if (!protocolContent) return null
    if (!searchQuery.trim() || searchMatches.length === 0) {
      return <pre className="whitespace-pre-wrap font-sans text-gray-800 leading-relaxed">{protocolContent}</pre>
    }

    // Build highlighted content
    const parts: React.ReactNode[] = []
    let lastIndex = 0

    searchMatches.forEach((match, i) => {
      // Add text before match
      if (match.start > lastIndex) {
        parts.push(
          <span key={`text-${i}`}>{protocolContent.slice(lastIndex, match.start)}</span>
        )
      }
      // Add highlighted match
      parts.push(
        <mark
          key={`match-${i}`}
          className={`search-highlight ${i === currentMatchIndex ? 'bg-orange-400' : 'bg-yellow-200'}`}
        >
          {protocolContent.slice(match.start, match.end)}
        </mark>
      )
      lastIndex = match.end
    })

    // Add remaining text
    if (lastIndex < protocolContent.length) {
      parts.push(<span key="text-end">{protocolContent.slice(lastIndex)}</span>)
    }

    return <pre className="whitespace-pre-wrap font-sans text-gray-800 leading-relaxed">{parts}</pre>
  }, [protocolContent, searchQuery, searchMatches, currentMatchIndex])

  // Loading state
  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600 mx-auto" />
          <p className="mt-3 text-gray-600">Loading protocol...</p>
        </div>
      </div>
    )
  }

  // Error state
  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="text-center max-w-md">
          <AlertCircle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Failed to Load Protocol</h2>
          <p className="text-gray-600">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      {/* Top Toolbar */}
      <div className="bg-white border-b px-4 py-2 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-blue-600" />
            <div>
              <h1 className="font-semibold text-gray-900 text-sm">{protocolTitle}</h1>
              <p className="text-xs text-gray-500">{protocolFilename} | {protocolContent.length.toLocaleString()} chars</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-6">
          {/* Zoom Controls */}
          <div className="flex items-center gap-1 border-r pr-4">
            <button
              onClick={handleZoomOut}
              className="p-1.5 hover:bg-gray-100 rounded transition-colors"
              disabled={zoom <= 50}
            >
              <ZoomOut className="w-4 h-4 text-gray-600" />
            </button>
            <button
              onClick={handleZoomReset}
              className="px-2 py-1 text-sm text-gray-600 hover:bg-gray-100 rounded min-w-[60px] text-center"
            >
              {zoom}%
            </button>
            <button
              onClick={handleZoomIn}
              className="p-1.5 hover:bg-gray-100 rounded transition-colors"
              disabled={zoom >= 200}
            >
              <ZoomIn className="w-4 h-4 text-gray-600" />
            </button>
          </div>

          {/* Search */}
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search in protocol..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 pr-4 py-1.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 w-64"
              />
            </div>
            {searchMatches.length > 0 && (
              <div className="flex items-center gap-1">
                <span className="text-sm text-gray-500">
                  {currentMatchIndex + 1} / {searchMatches.length}
                </span>
                <button
                  onClick={goToPrevMatch}
                  className="p-1 hover:bg-gray-100 rounded"
                  title="Previous match"
                >
                  <ChevronUp className="w-4 h-4 text-gray-600" />
                </button>
                <button
                  onClick={goToNextMatch}
                  className="p-1 hover:bg-gray-100 rounded"
                  title="Next match"
                >
                  <ChevronDown className="w-4 h-4 text-gray-600" />
                </button>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1">
            <button
              onClick={toggleFactDrawer}
              className={`px-3 py-1.5 text-sm font-medium rounded-lg transition-colors flex items-center gap-2 ${
                ui.factDrawerOpen
                  ? 'bg-indigo-600 text-white'
                  : 'bg-indigo-50 text-indigo-600 hover:bg-indigo-100'
              }`}
            >
              <BookOpen className="w-4 h-4" />
              Extracted Facts
            </button>
            <button
              onClick={handleSwitchToAuthoring}
              className="px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 rounded-lg transition-colors flex items-center gap-2"
            >
              <Maximize2 className="w-4 h-4" />
              SAP Editor
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Protocol Viewer - Full Width */}
        <div className="flex-1 bg-gray-100 overflow-hidden">
          <div
            ref={containerRef}
            className="h-full overflow-y-auto p-6"
            onScroll={handleScroll}
          >
            {protocolContent ? (
              <div
                ref={contentRef}
                className="max-w-4xl mx-auto bg-white rounded-lg shadow-sm p-8 border border-gray-200"
                style={{ fontSize: `${zoom}%` }}
              >
                {highlightedContent}
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center">
                <FileText className="w-16 h-16 text-gray-300 mb-4" />
                <h2 className="text-xl font-semibold text-gray-700 mb-2">No Protocol Content</h2>
                <p className="text-gray-500">
                  The protocol content could not be loaded or is empty.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Floating Fact Drawer */}
        <FloatingFactDrawer
          isOpen={ui.factDrawerOpen}
          onClose={closeFactDrawer}
        />
      </div>
    </div>
  )
}

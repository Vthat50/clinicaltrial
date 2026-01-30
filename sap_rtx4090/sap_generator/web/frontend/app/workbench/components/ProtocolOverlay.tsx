'use client'

import { useEffect, useRef } from 'react'
import {
  X,
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Search,
  FileText,
  Maximize2,
} from 'lucide-react'
import { useWorkspaceStore } from '../stores/workspaceStore'

interface ProtocolOverlayProps {
  isOpen: boolean
  onClose: () => void
  protocolUrl?: string
  totalPages?: number
}

export default function ProtocolOverlay({
  isOpen,
  onClose,
  protocolUrl,
  totalPages = 0,
}: ProtocolOverlayProps) {
  const {
    scroll,
    setProtocolScroll,
    teleportTarget,
    clearTeleport,
    setViewMode,
  } = useWorkspaceStore()

  const containerRef = useRef<HTMLDivElement>(null)

  // Handle teleport to specific page
  useEffect(() => {
    if (teleportTarget?.sourceId && isOpen) {
      // Parse sourceId to get page number (e.g., "page_42" -> 42)
      const match = teleportTarget.sourceId.match(/page_(\d+)/)
      if (match) {
        const pageNum = parseInt(match[1], 10)
        // Scroll to page (simplified - in real impl would calculate exact position)
        if (containerRef.current) {
          containerRef.current.scrollTop = pageNum * 800 // Approximate page height
        }
      }
      clearTeleport()
    }
  }, [teleportTarget, isOpen, clearTeleport])

  // Restore scroll position on open
  useEffect(() => {
    if (isOpen && containerRef.current) {
      containerRef.current.scrollTop = scroll.protocol
    }
  }, [isOpen])

  // Save scroll position on scroll
  const handleScroll = () => {
    if (containerRef.current) {
      setProtocolScroll(containerRef.current.scrollTop)
    }
  }

  const handleExpandToFullView = () => {
    setViewMode('protocol-audit')
    onClose()
  }

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40 transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Overlay Panel */}
      <div
        className={`
          fixed left-16 top-0 h-full w-[40vw] bg-white shadow-2xl z-50
          flex flex-col transform transition-transform duration-300 ease-out
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        {/* Header */}
        <div className="px-4 py-3 border-b bg-gradient-to-r from-blue-50 to-white flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <FileText className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900">Protocol Reference</h2>
              <p className="text-xs text-gray-500">Quick view - Click to expand</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleExpandToFullView}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              title="Expand to Full View"
            >
              <Maximize2 className="w-4 h-4 text-gray-500" />
            </button>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          </div>
        </div>

        {/* Toolbar */}
        <div className="px-4 py-2 border-b flex items-center justify-between bg-gray-50 shrink-0">
          <div className="flex items-center gap-2">
            <button className="p-1.5 hover:bg-gray-200 rounded transition-colors">
              <ZoomOut className="w-4 h-4 text-gray-600" />
            </button>
            <span className="text-sm text-gray-600 w-12 text-center">100%</span>
            <button className="p-1.5 hover:bg-gray-200 rounded transition-colors">
              <ZoomIn className="w-4 h-4 text-gray-600" />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <button className="p-1.5 hover:bg-gray-200 rounded transition-colors">
              <ChevronLeft className="w-4 h-4 text-gray-600" />
            </button>
            <span className="text-sm text-gray-600">
              Page 1 / {totalPages || '—'}
            </span>
            <button className="p-1.5 hover:bg-gray-200 rounded transition-colors">
              <ChevronRight className="w-4 h-4 text-gray-600" />
            </button>
          </div>
          <div className="relative">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search..."
              className="pl-8 pr-3 py-1 text-sm border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 w-32"
            />
          </div>
        </div>

        {/* Protocol Content */}
        <div
          ref={containerRef}
          className="flex-1 overflow-y-auto bg-gray-100"
          onScroll={handleScroll}
        >
          {protocolUrl ? (
            <iframe
              src={protocolUrl}
              className="w-full h-full border-0"
              title="Protocol Document"
            />
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-gray-500 p-8">
              <FileText className="w-16 h-16 text-gray-300 mb-4" />
              <p className="text-lg font-medium text-gray-700 mb-2">Protocol Document</p>
              <p className="text-sm text-center text-gray-500 max-w-sm">
                The uploaded protocol document will be displayed here for reference while authoring the SAP.
              </p>
              <div className="mt-8 space-y-4 w-full max-w-md">
                {/* Placeholder pages */}
                {[1, 2, 3].map((page) => (
                  <div
                    key={page}
                    className="bg-white rounded-lg shadow-sm p-6 border border-gray-200"
                  >
                    <div className="flex items-center justify-between mb-4">
                      <div className="h-3 w-32 bg-gray-200 rounded" />
                      <span className="text-xs text-gray-400">Page {page}</span>
                    </div>
                    <div className="space-y-2">
                      <div className="h-2 w-full bg-gray-100 rounded" />
                      <div className="h-2 w-5/6 bg-gray-100 rounded" />
                      <div className="h-2 w-4/6 bg-gray-100 rounded" />
                      <div className="h-2 w-full bg-gray-100 rounded" />
                      <div className="h-2 w-3/4 bg-gray-100 rounded" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t bg-gray-50 flex items-center justify-between shrink-0">
          <p className="text-xs text-gray-500">
            Press <kbd className="px-1.5 py-0.5 bg-gray-200 rounded text-xs">Esc</kbd> to close
          </p>
          <button
            onClick={handleExpandToFullView}
            className="text-xs text-indigo-600 hover:text-indigo-700 font-medium"
          >
            Open Full Protocol View
          </button>
        </div>
      </div>
    </>
  )
}

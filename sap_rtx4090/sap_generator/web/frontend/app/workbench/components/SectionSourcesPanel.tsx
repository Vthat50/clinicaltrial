'use client'

import { X, Database, FileText, Tags, Clock } from 'lucide-react'
import type { SAPSection, KBToolUsed } from '@/lib/types'

interface SectionSourcesPanelProps {
  section: SAPSection | null
  isOpen: boolean
  onClose: () => void
}

export default function SectionSourcesPanel({ section, isOpen, onClose }: SectionSourcesPanelProps) {
  if (!isOpen || !section) return null

  const hasKBTools = section.kb_tools_used && section.kb_tools_used.length > 0
  const hasProtocolExcerpts = section.protocol_excerpts_used && section.protocol_excerpts_used.length > 0
  const hasMetadata = section.metadata_used && section.metadata_used.length > 0
  const hasSources = hasKBTools || hasProtocolExcerpts || hasMetadata

  return (
    <div className="w-80 border-l bg-gray-50 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b bg-white flex items-center justify-between">
        <h3 className="font-semibold text-gray-900">Section Sources</h3>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-100 rounded transition-colors"
        >
          <X className="w-4 h-4 text-gray-500" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {!hasSources ? (
          <div className="text-center py-8 text-gray-500">
            <Database className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No sources tracked yet</p>
            <p className="text-xs mt-1">Generate this section to see sources</p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* KB Tools Used */}
            {hasKBTools && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Database className="w-4 h-4 text-blue-600" />
                  <h4 className="text-sm font-medium text-gray-700">
                    Knowledge Base Tools
                  </h4>
                  <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full">
                    {section.kb_tools_used.length}
                  </span>
                </div>
                <div className="space-y-2">
                  {section.kb_tools_used.map((tool, i) => (
                    <KBToolCard key={i} tool={tool} />
                  ))}
                </div>
              </div>
            )}

            {/* Protocol Excerpts */}
            {hasProtocolExcerpts && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <FileText className="w-4 h-4 text-green-600" />
                  <h4 className="text-sm font-medium text-gray-700">
                    Protocol Excerpts
                  </h4>
                  <span className="text-xs bg-green-100 text-green-700 px-1.5 py-0.5 rounded-full">
                    {section.protocol_excerpts_used.length}
                  </span>
                </div>
                <div className="space-y-2">
                  {section.protocol_excerpts_used.map((excerpt, i) => (
                    <div
                      key={i}
                      className="text-sm p-2 bg-white rounded border border-gray-200 text-gray-600"
                    >
                      <p className="line-clamp-3">"{excerpt}"</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Metadata Fields */}
            {hasMetadata && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Tags className="w-4 h-4 text-purple-600" />
                  <h4 className="text-sm font-medium text-gray-700">
                    Metadata Fields
                  </h4>
                  <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded-full">
                    {section.metadata_used.length}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1">
                  {section.metadata_used.map((field, i) => (
                    <span
                      key={i}
                      className="text-xs bg-white border border-gray-200 px-2 py-1 rounded text-gray-600"
                    >
                      {field}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer with generation time */}
      {section.generated_at && (
        <div className="p-3 border-t bg-white">
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Clock className="w-3 h-3" />
            <span>Generated: {new Date(section.generated_at).toLocaleString()}</span>
          </div>
        </div>
      )}
    </div>
  )
}

function KBToolCard({ tool }: { tool: KBToolUsed }) {
  return (
    <div className="text-sm p-3 bg-white rounded border border-gray-200">
      <div className="font-medium text-blue-600 mb-1">
        {formatToolName(tool.tool_name)}
      </div>
      {tool.description && (
        <div className="text-gray-500 text-xs mb-2">{tool.description}</div>
      )}
      <div className="text-gray-400 text-xs font-mono">
        <div>{tool.source_file}</div>
        <div className="text-gray-300">→ {tool.source_key}</div>
      </div>
    </div>
  )
}

function formatToolName(name: string): string {
  // Convert snake_case to Title Case
  return name
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

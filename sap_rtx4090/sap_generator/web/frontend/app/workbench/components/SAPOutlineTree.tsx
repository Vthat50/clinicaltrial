'use client'

import { useState, useMemo } from 'react'
import {
  ChevronDown,
  ChevronRight,
  FileText,
  CheckCircle,
  Edit3,
  Clock,
  Loader2,
  Search,
  ChevronsUpDown,
  Play,
} from 'lucide-react'
import { useWorkspaceStore, SAPSection } from '../stores/workspaceStore'

interface StatusBadgeProps {
  status: SAPSection['status']
  compact?: boolean
}

function StatusBadge({ status, compact = false }: StatusBadgeProps) {
  const config = {
    not_started: { icon: <Clock className="w-3 h-3" />, color: 'text-gray-400', bg: 'bg-gray-100', label: 'Not Started' },
    draft: { icon: <FileText className="w-3 h-3" />, color: 'text-yellow-600', bg: 'bg-yellow-100', label: 'Draft' },
    edited: { icon: <Edit3 className="w-3 h-3" />, color: 'text-blue-600', bg: 'bg-blue-100', label: 'Edited' },
    approved: { icon: <CheckCircle className="w-3 h-3" />, color: 'text-green-600', bg: 'bg-green-100', label: 'Approved' },
    generating: { icon: <Loader2 className="w-3 h-3 animate-spin" />, color: 'text-purple-600', bg: 'bg-purple-100', label: 'Generating' },
  }[status]

  if (compact) {
    return (
      <span className={`${config.color}`} title={config.label}>
        {config.icon}
      </span>
    )
  }

  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs ${config.bg} ${config.color}`}>
      {config.icon}
      <span className="hidden xl:inline">{config.label}</span>
    </span>
  )
}

interface SectionItemProps {
  section: SAPSection
  depth: number
  isSelected: boolean
  onSelect: (id: string) => void
  onGenerate: (id: string) => Promise<void>
}

function SectionItem({ section, depth, isSelected, onSelect, onGenerate }: SectionItemProps) {
  const [isExpanded, setIsExpanded] = useState(depth < 1)
  const hasChildren = section.children && section.children.length > 0

  return (
    <div>
      <div
        className={`
          group flex items-center gap-1 py-1.5 px-2 rounded-md cursor-pointer
          transition-colors text-sm
          ${isSelected
            ? 'bg-indigo-50 text-indigo-700 font-medium'
            : 'hover:bg-gray-100 text-gray-700'
          }
        `}
        style={{ paddingLeft: `${8 + depth * 12}px` }}
        onClick={() => onSelect(section.id)}
      >
        {/* Expand/collapse for items with children */}
        {hasChildren ? (
          <button
            onClick={(e) => {
              e.stopPropagation()
              setIsExpanded(!isExpanded)
            }}
            className="p-0.5 hover:bg-gray-200 rounded"
          >
            {isExpanded ? (
              <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
            )}
          </button>
        ) : (
          <span className="w-4" />
        )}

        {/* Status indicator dot */}
        <span
          className={`w-1.5 h-1.5 rounded-full shrink-0 ${
            section.status === 'approved'
              ? 'bg-green-500'
              : section.status === 'draft' || section.status === 'edited'
              ? 'bg-yellow-500'
              : section.status === 'generating'
              ? 'bg-purple-500 animate-pulse'
              : 'bg-gray-300'
          }`}
        />

        {/* Section name */}
        <span className="flex-1 truncate">{section.display_name || section.name}</span>

        {/* Version badge */}
        {section.version > 1 && (
          <span className="text-[10px] text-gray-400 bg-gray-100 px-1 rounded">
            v{section.version}
          </span>
        )}

        {/* Quick generate button */}
        {!section.has_content && section.status !== 'generating' && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onGenerate(section.id)
            }}
            className="opacity-0 group-hover:opacity-100 p-1 hover:bg-indigo-100 rounded transition-opacity"
            title="Generate section"
          >
            <Play className="w-3 h-3 text-indigo-600" />
          </button>
        )}
      </div>

      {/* Children */}
      {hasChildren && isExpanded && (
        <div>
          {section.children!.map((child) => (
            <SectionItem
              key={child.id}
              section={child}
              depth={depth + 1}
              isSelected={isSelected}
              onSelect={onSelect}
              onGenerate={onGenerate}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface SAPOutlineTreeProps {
  isCollapsed: boolean
  onToggleCollapse: () => void
  onGenerateSection: (sectionId: string) => Promise<void>
}

export default function SAPOutlineTree({
  isCollapsed,
  onToggleCollapse,
  onGenerateSection,
}: SAPOutlineTreeProps) {
  const { outline, selectedSectionId, selectSection } = useWorkspaceStore()
  const [searchQuery, setSearchQuery] = useState('')
  const [expandAll, setExpandAll] = useState(false)

  // Filter sections based on search
  const filteredOutline = useMemo(() => {
    if (!searchQuery) return outline

    const matchesSearch = (section: SAPSection): boolean => {
      const matches = section.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        section.display_name?.toLowerCase().includes(searchQuery.toLowerCase())

      if (matches) return true
      if (section.children) {
        return section.children.some(matchesSearch)
      }
      return false
    }

    const filterTree = (sections: SAPSection[]): SAPSection[] => {
      return sections
        .filter(matchesSearch)
        .map((section) => ({
          ...section,
          children: section.children ? filterTree(section.children) : undefined,
        }))
    }

    return filterTree(outline)
  }, [outline, searchQuery])

  // Flatten sections helper
  const flattenSections = (sections: SAPSection[]): SAPSection[] => {
    return sections.flatMap((s) => [s, ...(s.children ? flattenSections(s.children) : [])])
  }

  // Calculate progress stats
  const stats = useMemo(() => {
    const allSections = flattenSections(outline)
    return {
      total: allSections.length,
      approved: allSections.filter((s) => s.status === 'approved').length,
      draft: allSections.filter((s) => s.status === 'draft' || s.status === 'edited').length,
      notStarted: allSections.filter((s) => s.status === 'not_started').length,
    }
  }, [outline])

  // Generate all remaining sections
  const [isGeneratingAll, setIsGeneratingAll] = useState(false)

  const handleGenerateAllRemaining = async () => {
    const allSections = flattenSections(outline)
    const remainingSections = allSections.filter((s) => s.status === 'not_started')

    if (remainingSections.length === 0) {
      alert('No remaining sections to generate!')
      return
    }

    setIsGeneratingAll(true)

    // Generate sections sequentially to avoid overwhelming the API
    for (const section of remainingSections) {
      try {
        await onGenerateSection(section.id)
      } catch (error) {
        console.error(`Failed to generate section ${section.id}:`, error)
      }
    }

    setIsGeneratingAll(false)
  }

  if (isCollapsed) {
    return (
      <div className="w-12 h-full bg-white border-r flex flex-col items-center py-4 shrink-0">
        <button
          onClick={onToggleCollapse}
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          title="Expand Outline"
        >
          <ChevronRight className="w-5 h-5 text-gray-500" />
        </button>

        {/* Mini progress */}
        <div className="mt-4 flex flex-col gap-1">
          <div
            className="w-2 h-2 rounded-full bg-green-500"
            title={`${stats.approved} approved`}
          />
          <div
            className="w-2 h-2 rounded-full bg-yellow-500"
            title={`${stats.draft} drafts`}
          />
          <div
            className="w-2 h-2 rounded-full bg-gray-300"
            title={`${stats.notStarted} not started`}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="w-64 h-full bg-white border-r flex flex-col shrink-0">
      {/* Header */}
      <div className="px-3 py-3 border-b flex items-center justify-between shrink-0">
        <h3 className="font-medium text-gray-900 text-sm">SAP Outline</h3>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setExpandAll(!expandAll)}
            className="p-1.5 hover:bg-gray-100 rounded transition-colors"
            title={expandAll ? 'Collapse All' : 'Expand All'}
          >
            <ChevronsUpDown className="w-4 h-4 text-gray-400" />
          </button>
          <button
            onClick={onToggleCollapse}
            className="p-1.5 hover:bg-gray-100 rounded transition-colors"
            title="Collapse Panel"
          >
            <ChevronRight className="w-4 h-4 text-gray-400 rotate-180" />
          </button>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="px-3 py-2 border-b shrink-0">
        <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
          <span>{stats.approved} / {stats.total} sections</span>
          <span>{Math.round((stats.approved / stats.total) * 100) || 0}%</span>
        </div>
        <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden flex">
          <div
            className="bg-green-500 transition-all duration-300"
            style={{ width: `${(stats.approved / stats.total) * 100}%` }}
          />
          <div
            className="bg-yellow-500 transition-all duration-300"
            style={{ width: `${(stats.draft / stats.total) * 100}%` }}
          />
        </div>
      </div>

      {/* Search */}
      <div className="px-3 py-2 border-b shrink-0">
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search sections..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
          />
        </div>
      </div>

      {/* Sections Tree */}
      <div className="flex-1 overflow-y-auto py-2">
        {filteredOutline.length === 0 ? (
          <div className="px-3 py-8 text-center text-gray-500">
            <FileText className="w-8 h-8 mx-auto mb-2 text-gray-300" />
            <p className="text-sm">No sections found</p>
          </div>
        ) : (
          filteredOutline.map((section) => (
            <SectionItem
              key={section.id}
              section={section}
              depth={0}
              isSelected={selectedSectionId === section.id}
              onSelect={selectSection}
              onGenerate={onGenerateSection}
            />
          ))
        )}
      </div>

      {/* Footer Actions */}
      <div className="px-3 py-2 border-t bg-gray-50 shrink-0">
        <button
          onClick={handleGenerateAllRemaining}
          disabled={isGeneratingAll || stats.notStarted === 0}
          className={`w-full py-2 text-sm font-medium border rounded-md transition-colors flex items-center justify-center gap-2 ${
            isGeneratingAll || stats.notStarted === 0
              ? 'text-gray-400 border-gray-200 bg-gray-100 cursor-not-allowed'
              : 'text-indigo-600 border-indigo-200 hover:bg-indigo-50'
          }`}
        >
          {isGeneratingAll ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Generating ({stats.notStarted} remaining)...
            </>
          ) : (
            <>
              <Play className="w-4 h-4" />
              Generate All Remaining ({stats.notStarted})
            </>
          )}
        </button>
      </div>
    </div>
  )
}

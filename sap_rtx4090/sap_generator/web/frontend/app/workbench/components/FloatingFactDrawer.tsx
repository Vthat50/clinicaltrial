'use client'

import { useState, useMemo, useEffect } from 'react'
import {
  X,
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  HelpCircle,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Edit3,
  Search,
  Filter,
  Target,
  Users,
  Beaker,
  Activity,
  Layers,
  Scissors,
  Ban,
  Dna,
  FileText,
} from 'lucide-react'
import { useWorkspaceStore, ExtractionFact, FactStatus, selectFlaggedFacts } from '../stores/workspaceStore'

// Category configuration with icons and colors
const CATEGORY_CONFIG: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  study_info: { icon: <FileText className="w-4 h-4" />, color: 'text-blue-600', label: 'Study Information' },
  endpoints: { icon: <Target className="w-4 h-4" />, color: 'text-indigo-600', label: 'Endpoints' },
  populations: { icon: <Users className="w-4 h-4" />, color: 'text-green-600', label: 'Populations' },
  sample_size: { icon: <Activity className="w-4 h-4" />, color: 'text-purple-600', label: 'Sample Size' },
  subgroups: { icon: <Layers className="w-4 h-4" />, color: 'text-amber-600', label: 'Subgroups' },
  censoring: { icon: <Scissors className="w-4 h-4" />, color: 'text-gray-600', label: 'Censoring Rules' },
  prohibitions: { icon: <Ban className="w-4 h-4" />, color: 'text-red-600', label: 'Prohibitions' },
  cart_specific: { icon: <Dna className="w-4 h-4" />, color: 'text-purple-600', label: 'CAR-T Specific' },
  design: { icon: <Beaker className="w-4 h-4" />, color: 'text-cyan-600', label: 'Study Design' },
}

const STATUS_CONFIG: Record<FactStatus, { icon: React.ReactNode; color: string; bg: string; label: string }> = {
  verified: { icon: <CheckCircle className="w-4 h-4" />, color: 'text-green-600', bg: 'bg-green-50', label: 'Verified' },
  flagged: { icon: <AlertCircle className="w-4 h-4" />, color: 'text-red-600', bg: 'bg-red-50', label: 'Flagged' },
  warning: { icon: <AlertTriangle className="w-4 h-4" />, color: 'text-amber-600', bg: 'bg-amber-50', label: 'Warning' },
  unverified: { icon: <HelpCircle className="w-4 h-4" />, color: 'text-gray-400', bg: 'bg-gray-50', label: 'Unverified' },
}

interface FactCardProps {
  fact: ExtractionFact
  onViewInProtocol: (fact: ExtractionFact) => void
  onEdit: (factId: string) => void
  isEditing: boolean
  onSave: (fact: ExtractionFact) => void
  onCancel: () => void
}

function FactCard({ fact, onViewInProtocol, onEdit, isEditing, onSave, onCancel }: FactCardProps) {
  const statusConfig = STATUS_CONFIG[fact.status]
  const [editedValue, setEditedValue] = useState(
    typeof fact.value === 'boolean' ? (fact.value ? 'Yes' : 'No') : (fact.value?.toString() || '')
  )
  const [editedStatus, setEditedStatus] = useState<FactStatus>(fact.status)

  // Reset form when editing starts
  useEffect(() => {
    if (isEditing) {
      setEditedValue(typeof fact.value === 'boolean' ? (fact.value ? 'Yes' : 'No') : (fact.value?.toString() || ''))
      setEditedStatus(fact.status)
    }
  }, [isEditing, fact])

  // Build tooltip for the View in Protocol button
  const getTooltip = () => {
    if (fact.source_section) return `View in Protocol (${fact.source_section})`
    if (fact.source_quote) return 'View in Protocol (has quote)'
    return 'Search in Protocol'
  }

  const handleSave = () => {
    onSave({
      ...fact,
      value: editedValue,
      status: editedStatus,
      warning_message: editedStatus === 'verified' ? undefined : fact.warning_message,
    })
  }

  // Edit mode UI
  if (isEditing) {
    return (
      <div className="p-3 rounded-lg border bg-blue-50 border-blue-300">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Edit3 className="w-4 h-4 text-blue-600" />
            <span className="font-medium text-sm text-gray-900">{fact.name}</span>
          </div>

          {/* Value editor */}
          <div>
            <label className="text-xs text-gray-600 mb-1 block">Value</label>
            <input
              type="text"
              value={editedValue}
              onChange={(e) => setEditedValue(e.target.value)}
              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Status selector */}
          <div>
            <label className="text-xs text-gray-600 mb-1 block">Status</label>
            <select
              value={editedStatus}
              onChange={(e) => setEditedStatus(e.target.value as FactStatus)}
              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="verified">Verified</option>
              <option value="flagged">Flagged</option>
              <option value="warning">Warning</option>
              <option value="unverified">Unverified</option>
            </select>
          </div>

          {/* Save/Cancel buttons */}
          <div className="flex gap-2 pt-1">
            <button
              onClick={handleSave}
              className="flex-1 px-3 py-1.5 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 transition-colors"
            >
              Save
            </button>
            <button
              onClick={onCancel}
              className="flex-1 px-3 py-1.5 text-sm font-medium text-gray-700 bg-gray-100 rounded hover:bg-gray-200 transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Normal display mode
  return (
    <div className={`p-3 rounded-lg border ${statusConfig.bg} border-gray-200`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={statusConfig.color}>{statusConfig.icon}</span>
            <span className="font-medium text-sm text-gray-900 truncate">{fact.name}</span>
          </div>
          <p className="text-sm text-gray-700 mt-1">
            {typeof fact.value === 'boolean'
              ? fact.value ? 'Yes' : 'No'
              : fact.value ?? '-'}
          </p>
          {fact.definition && (
            <p className="text-xs text-gray-500 mt-1 line-clamp-2">{fact.definition}</p>
          )}
          {fact.source_section && (
            <p className="text-xs text-indigo-600 mt-1">{fact.source_section}</p>
          )}
          {fact.warning_message && (
            <p className="text-xs text-amber-700 mt-1 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" />
              {fact.warning_message}
            </p>
          )}
        </div>
        <div className="flex flex-col gap-1">
          {/* Always show View in Protocol button - uses smart fallback search */}
          <button
            onClick={() => onViewInProtocol(fact)}
            className="p-1.5 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-colors"
            title={getTooltip()}
          >
            <ExternalLink className="w-4 h-4" />
          </button>
          <button
            onClick={() => onEdit(fact.id)}
            className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded transition-colors"
            title="Edit Fact"
          >
            <Edit3 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

interface CategorySectionProps {
  category: string
  facts: ExtractionFact[]
  defaultOpen?: boolean
  onViewInProtocol: (fact: ExtractionFact) => void
  onEditFact: (factId: string) => void
  editingFactId: string | null
  onSaveFact: (fact: ExtractionFact) => void
  onCancelEdit: () => void
}

function CategorySection({ category, facts, defaultOpen = false, onViewInProtocol, onEditFact, editingFactId, onSaveFact, onCancelEdit }: CategorySectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const config = CATEGORY_CONFIG[category] || { icon: <FileText className="w-4 h-4" />, color: 'text-gray-600', label: category }

  const flaggedCount = facts.filter(f => f.status === 'flagged' || f.status === 'warning').length

  return (
    <div className="border-b border-gray-100 last:border-b-0">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className={config.color}>{config.icon}</span>
          <span className="font-medium text-gray-900">{config.label}</span>
          <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full">
            {facts.length}
          </span>
          {flaggedCount > 0 && (
            <span className="text-xs text-red-600 bg-red-100 px-2 py-0.5 rounded-full">
              {flaggedCount} issues
            </span>
          )}
        </div>
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronRight className="w-4 h-4 text-gray-400" />
        )}
      </button>
      {isOpen && (
        <div className="px-4 pb-4 space-y-2">
          {facts.map((fact) => (
            <FactCard
              key={fact.id}
              fact={fact}
              onViewInProtocol={onViewInProtocol}
              onEdit={onEditFact}
              isEditing={editingFactId === fact.id}
              onSave={onSaveFact}
              onCancel={onCancelEdit}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface FloatingFactDrawerProps {
  isOpen: boolean
  onClose: () => void
}

export default function FloatingFactDrawer({ isOpen, onClose }: FloatingFactDrawerProps) {
  const { facts, teleportToProtocol, selectFact, openFactDrawer, updateFact } = useWorkspaceStore()
  const flaggedFacts = useWorkspaceStore(selectFlaggedFacts)

  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<FactStatus | 'all'>('all')
  const [editingFactId, setEditingFactId] = useState<string | null>(null)

  // Group facts by category
  const groupedFacts = useMemo(() => {
    const filtered = facts.filter((fact) => {
      const matchesSearch = searchQuery === '' ||
        fact.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (fact.value?.toString().toLowerCase().includes(searchQuery.toLowerCase()))

      const matchesStatus = statusFilter === 'all' || fact.status === statusFilter

      return matchesSearch && matchesStatus
    })

    return filtered.reduce((acc, fact) => {
      const category = fact.category || 'other'
      if (!acc[category]) {
        acc[category] = []
      }
      acc[category].push(fact)
      return acc
    }, {} as Record<string, ExtractionFact[]>)
  }, [facts, searchQuery, statusFilter])

  const handleViewInProtocol = (fact: ExtractionFact) => {
    // Build smart fallback search text from available data
    const searchText = fact.definition
      || (typeof fact.value === 'string' ? fact.value : fact.value?.toString())
      || fact.name

    teleportToProtocol(
      fact.source_quote || null,
      fact.source_section || null,
      searchText
    )
  }

  const handleEditFact = (factId: string) => {
    setEditingFactId(factId)
  }

  const handleSaveFact = (fact: ExtractionFact) => {
    updateFact(fact.id, {
      value: fact.value,
      status: fact.status,
      warning_message: fact.warning_message,
    })
    setEditingFactId(null)
  }

  const handleCancelEdit = () => {
    setEditingFactId(null)
  }

  // Categories in display order
  const categoryOrder = [
    'study_info',
    'design',
    'endpoints',
    'populations',
    'sample_size',
    'subgroups',
    'censoring',
    'prohibitions',
    'cart_specific',
  ]

  const orderedCategories = categoryOrder.filter((cat) => groupedFacts[cat]?.length > 0)
  const otherCategories = Object.keys(groupedFacts).filter((cat) => !categoryOrder.includes(cat))

  return (
    <>
      {/* Backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/20 z-40 transition-opacity"
          onClick={onClose}
        />
      )}

      {/* Drawer */}
      <div
        className={`
          fixed right-0 top-0 h-full w-[400px] bg-white shadow-2xl z-50
          flex flex-col transform transition-transform duration-300 ease-out
          ${isOpen ? 'translate-x-0' : 'translate-x-full'}
        `}
      >
        {/* Header */}
        <div className="px-4 py-3 border-b bg-gradient-to-r from-indigo-50 to-white flex items-center justify-between shrink-0">
          <div>
            <h2 className="font-semibold text-gray-900">Extracted Facts</h2>
            <p className="text-xs text-gray-500">55-Category Knowledge Graph</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Priority Alerts Banner */}
        {flaggedFacts.length > 0 && (
          <div className="px-4 py-3 bg-red-50 border-b border-red-100 shrink-0">
            <div className="flex items-center gap-2 text-red-700 mb-2">
              <AlertCircle className="w-4 h-4" />
              <span className="text-sm font-medium">{flaggedFacts.length} items need attention</span>
            </div>
            <div className="space-y-1 max-h-32 overflow-y-auto">
              {flaggedFacts.slice(0, 3).map((fact) => (
                <button
                  key={fact.id}
                  onClick={() => {
                    selectFact(fact.id)
                    if (fact.source_quote || fact.source_section) {
                      handleViewInProtocol(fact)
                    }
                  }}
                  className="w-full text-left p-2 bg-white rounded border border-red-200 hover:border-red-300 transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-900 truncate">{fact.name}</span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${
                      fact.status === 'flagged' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'
                    }`}>
                      {fact.status}
                    </span>
                  </div>
                  {fact.warning_message && (
                    <p className="text-xs text-red-600 mt-0.5 truncate">{fact.warning_message}</p>
                  )}
                </button>
              ))}
              {flaggedFacts.length > 3 && (
                <p className="text-xs text-red-600 text-center py-1">
                  +{flaggedFacts.length - 3} more issues
                </p>
              )}
            </div>
          </div>
        )}

        {/* Search & Filter */}
        <div className="px-4 py-3 border-b space-y-2 shrink-0">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search facts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as FactStatus | 'all')}
              className="flex-1 text-sm border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="all">All Status</option>
              <option value="flagged">Flagged</option>
              <option value="warning">Warning</option>
              <option value="verified">Verified</option>
              <option value="unverified">Unverified</option>
            </select>
          </div>
        </div>

        {/* Facts Grid */}
        <div className="flex-1 overflow-y-auto">
          {/* Priority: Show categories with issues first */}
          {orderedCategories.map((category) => (
            <CategorySection
              key={category}
              category={category}
              facts={groupedFacts[category]}
              defaultOpen={groupedFacts[category].some(f => f.status === 'flagged' || f.status === 'warning')}
              onViewInProtocol={handleViewInProtocol}
              onEditFact={handleEditFact}
              editingFactId={editingFactId}
              onSaveFact={handleSaveFact}
              onCancelEdit={handleCancelEdit}
            />
          ))}
          {otherCategories.map((category) => (
            <CategorySection
              key={category}
              category={category}
              facts={groupedFacts[category]}
              onViewInProtocol={handleViewInProtocol}
              onEditFact={handleEditFact}
              editingFactId={editingFactId}
              onSaveFact={handleSaveFact}
              onCancelEdit={handleCancelEdit}
            />
          ))}

          {/* Empty state */}
          {Object.keys(groupedFacts).length === 0 && (
            <div className="flex flex-col items-center justify-center h-64 text-gray-500">
              <Search className="w-8 h-8 mb-2 text-gray-300" />
              <p className="text-sm">No facts found</p>
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="text-sm text-indigo-600 hover:text-indigo-700 mt-1"
                >
                  Clear search
                </button>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t bg-gray-50 shrink-0">
          <p className="text-xs text-gray-500 text-center">
            {facts.length} facts extracted from protocol
          </p>
        </div>
      </div>
    </>
  )
}

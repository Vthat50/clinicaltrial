'use client'

import { FileText, ClipboardCheck, Layout, Activity, Settings, ChevronLeft } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useWorkspaceStore, ViewMode } from '../stores/workspaceStore'

interface RailButtonProps {
  icon: React.ReactNode
  label: string
  isActive?: boolean
  onClick: () => void
  badge?: number
  badgeColor?: string
}

function RailButton({ icon, label, isActive, onClick, badge, badgeColor = 'bg-red-500' }: RailButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`
        relative w-12 h-12 flex items-center justify-center rounded-xl
        transition-all duration-200 group
        ${isActive
          ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-200'
          : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'
        }
      `}
      title={label}
    >
      {icon}

      {/* Active indicator bar */}
      {isActive && (
        <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-indigo-600 rounded-r-full -ml-2" />
      )}

      {/* Badge */}
      {badge !== undefined && badge > 0 && (
        <span className={`absolute -top-1 -right-1 w-5 h-5 ${badgeColor} text-white text-xs font-medium rounded-full flex items-center justify-center`}>
          {badge > 9 ? '9+' : badge}
        </span>
      )}

      {/* Tooltip */}
      <span className="
        absolute left-full ml-3 px-2 py-1 bg-gray-900 text-white text-xs rounded
        opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-50
      ">
        {label}
      </span>
    </button>
  )
}

interface ContextRailProps {
  workspaceId: string
  flaggedCount?: number
  warningCount?: number
}

export default function ContextRail({ workspaceId, flaggedCount = 0, warningCount = 0 }: ContextRailProps) {
  const router = useRouter()
  const { viewMode, setViewMode, toggleFactDrawer, ui } = useWorkspaceStore()

  const totalAlerts = flaggedCount + warningCount

  return (
    <div className="w-16 h-full bg-white border-r border-gray-200 flex flex-col items-center py-4 shrink-0">
      {/* Back button */}
      <button
        onClick={() => router.push('/workbench')}
        className="w-10 h-10 flex items-center justify-center text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg mb-6 transition-colors"
        title="Back to Workspaces"
      >
        <ChevronLeft className="w-5 h-5" />
      </button>

      {/* Divider */}
      <div className="w-8 h-px bg-gray-200 mb-6" />

      {/* Main navigation */}
      <nav className="flex-1 flex flex-col items-center gap-2">
        {/* Protocol Audit View */}
        <RailButton
          icon={<FileText className="w-5 h-5" />}
          label="Protocol Viewer"
          isActive={viewMode === 'protocol-audit'}
          onClick={() => setViewMode('protocol-audit')}
        />

        {/* Validation / Fact Verification */}
        <RailButton
          icon={<ClipboardCheck className="w-5 h-5" />}
          label="Fact Verification"
          isActive={ui.factDrawerOpen && viewMode === 'protocol-audit'}
          onClick={() => {
            if (viewMode !== 'protocol-audit') {
              setViewMode('protocol-audit')
            }
            toggleFactDrawer()
          }}
          badge={totalAlerts}
          badgeColor={flaggedCount > 0 ? 'bg-red-500' : 'bg-amber-500'}
        />

        {/* Divider */}
        <div className="w-8 h-px bg-gray-200 my-2" />

        {/* SAP Outline */}
        <RailButton
          icon={<Layout className="w-5 h-5" />}
          label="SAP Authoring"
          isActive={viewMode === 'sap-authoring'}
          onClick={() => setViewMode('sap-authoring')}
        />

        {/* Activity / Generation Status */}
        <RailButton
          icon={<Activity className="w-5 h-5" />}
          label="Generation Activity"
          onClick={() => {
            // Could open an activity drawer
          }}
        />
      </nav>

      {/* Bottom section */}
      <div className="flex flex-col items-center gap-2 mt-auto">
        <div className="w-8 h-px bg-gray-200 mb-2" />
        <RailButton
          icon={<Settings className="w-5 h-5" />}
          label="Workspace Settings"
          onClick={() => {
            // Open settings modal
          }}
        />
      </div>
    </div>
  )
}

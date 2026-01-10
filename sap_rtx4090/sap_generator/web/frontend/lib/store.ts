/**
 * SAP Workbench State Management
 * Zustand store for workspace state
 */

import { create } from 'zustand'
import type {
  Workspace,
  MetadataResponse,
  SectionOutline,
  SectionContentResponse,
  SectionStatus,
} from './types'

// ============================================================================
// WORKSPACE STORE
// ============================================================================

interface WorkspaceState {
  // Current workspace
  workspace: Workspace | null
  metadata: MetadataResponse | null
  outline: SectionOutline[]

  // Section editor state
  selectedSectionId: string | null
  sectionContent: SectionContentResponse | null
  editContent: string
  isEditing: boolean
  isDirty: boolean

  // Generation state
  isGenerating: boolean
  generatingSection: string | null

  // UI state
  showProtocolPanel: boolean
  showProvenancePanel: boolean
  activeTab: 'metadata' | 'outline' | 'generate' | 'provenance' | 'export'

  // Actions
  setWorkspace: (workspace: Workspace | null) => void
  setMetadata: (metadata: MetadataResponse | null) => void
  setOutline: (outline: SectionOutline[]) => void

  selectSection: (sectionId: string | null) => void
  setSectionContent: (content: SectionContentResponse | null) => void
  setEditContent: (content: string) => void
  setIsEditing: (isEditing: boolean) => void
  setIsDirty: (isDirty: boolean) => void

  setIsGenerating: (isGenerating: boolean) => void
  setGeneratingSection: (sectionId: string | null) => void

  toggleProtocolPanel: () => void
  toggleProvenancePanel: () => void
  setActiveTab: (tab: 'metadata' | 'outline' | 'generate' | 'provenance' | 'export') => void

  // Update section status in outline
  updateSectionStatus: (sectionId: string, status: SectionStatus, hasContent?: boolean) => void

  // Reset store
  reset: () => void
}

const initialState = {
  workspace: null,
  metadata: null,
  outline: [],
  selectedSectionId: null,
  sectionContent: null,
  editContent: '',
  isEditing: false,
  isDirty: false,
  isGenerating: false,
  generatingSection: null,
  showProtocolPanel: true,
  showProvenancePanel: true,
  activeTab: 'metadata' as const,
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  ...initialState,

  setWorkspace: (workspace) => set({ workspace }),
  setMetadata: (metadata) => set({ metadata }),
  setOutline: (outline) => set({ outline }),

  selectSection: (sectionId) => set({
    selectedSectionId: sectionId,
    sectionContent: null,
    editContent: '',
    isEditing: false,
    isDirty: false,
  }),

  setSectionContent: (content) => set({
    sectionContent: content,
    editContent: content?.content || '',
    isDirty: false,
  }),

  setEditContent: (content) => set((state) => ({
    editContent: content,
    isDirty: content !== state.sectionContent?.content,
  })),

  setIsEditing: (isEditing) => set({ isEditing }),
  setIsDirty: (isDirty) => set({ isDirty }),

  setIsGenerating: (isGenerating) => set({ isGenerating }),
  setGeneratingSection: (sectionId) => set({ generatingSection: sectionId }),

  toggleProtocolPanel: () => set((state) => ({ showProtocolPanel: !state.showProtocolPanel })),
  toggleProvenancePanel: () => set((state) => ({ showProvenancePanel: !state.showProvenancePanel })),
  setActiveTab: (tab) => set({ activeTab: tab }),

  updateSectionStatus: (sectionId, status, hasContent) => set((state) => ({
    outline: state.outline.map((section) =>
      section.id === sectionId
        ? { ...section, status, has_content: hasContent ?? section.has_content }
        : section
    ),
  })),

  reset: () => set(initialState),
}))

// ============================================================================
// PORTFOLIO STORE
// ============================================================================

interface PortfolioState {
  workspaces: Workspace[]
  isLoading: boolean
  error: string | null

  // Filters
  phaseFilter: string
  statusFilter: string
  searchQuery: string

  // Actions
  setWorkspaces: (workspaces: Workspace[]) => void
  setIsLoading: (isLoading: boolean) => void
  setError: (error: string | null) => void
  setPhaseFilter: (phase: string) => void
  setStatusFilter: (status: string) => void
  setSearchQuery: (query: string) => void

  // Computed
  filteredWorkspaces: () => Workspace[]
}

export const usePortfolioStore = create<PortfolioState>((set, get) => ({
  workspaces: [],
  isLoading: true,
  error: null,
  phaseFilter: '',
  statusFilter: '',
  searchQuery: '',

  setWorkspaces: (workspaces) => set({ workspaces }),
  setIsLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  setPhaseFilter: (phase) => set({ phaseFilter: phase }),
  setStatusFilter: (status) => set({ statusFilter: status }),
  setSearchQuery: (query) => set({ searchQuery: query }),

  filteredWorkspaces: () => {
    const { workspaces, phaseFilter, statusFilter, searchQuery } = get()
    return workspaces.filter((ws) => {
      if (phaseFilter && ws.phase !== phaseFilter) return false
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        if (
          !ws.name.toLowerCase().includes(query) &&
          !ws.indication?.toLowerCase().includes(query)
        ) {
          return false
        }
      }
      return true
    })
  },
}))

// ============================================================================
// UI STORE
// ============================================================================

interface UIState {
  // Notifications
  notifications: { id: string; type: 'success' | 'error' | 'info'; message: string }[]

  // Global loading
  isGlobalLoading: boolean
  loadingMessage: string

  // Actions
  addNotification: (type: 'success' | 'error' | 'info', message: string) => void
  removeNotification: (id: string) => void
  setGlobalLoading: (isLoading: boolean, message?: string) => void
}

export const useUIStore = create<UIState>((set) => ({
  notifications: [],
  isGlobalLoading: false,
  loadingMessage: '',

  addNotification: (type, message) => {
    const id = Math.random().toString(36).slice(2)
    set((state) => ({
      notifications: [...state.notifications, { id, type, message }],
    }))
    // Auto-remove after 5 seconds
    setTimeout(() => {
      set((state) => ({
        notifications: state.notifications.filter((n) => n.id !== id),
      }))
    }, 5000)
  },

  removeNotification: (id) =>
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id),
    })),

  setGlobalLoading: (isLoading, message = 'Loading...') =>
    set({ isGlobalLoading: isLoading, loadingMessage: message }),
}))

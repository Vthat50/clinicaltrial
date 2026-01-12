import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// View modes for the layered task suite
export type ViewMode = 'protocol-audit' | 'sap-authoring'

// Fact verification status
export type FactStatus = 'verified' | 'flagged' | 'warning' | 'unverified'

// Extraction fact with verification info and provenance
export interface ExtractionFact {
  id: string
  category: string
  subcategory?: string
  name: string
  value: string | number | boolean | null
  definition?: string
  // Provenance - from extraction pipeline
  source_quote?: string // Verbatim text from protocol
  source_section?: string // Section number (e.g., "Section 6.1")
  // Legacy fields (deprecated)
  source_id?: string
  source_text?: string
  // Verification
  status: FactStatus
  confidence?: number
  warning_message?: string
}

// Section in the SAP outline
export interface SAPSection {
  id: string
  name: string
  display_name: string
  parent_id: string | null
  order: number
  level: number // 0 = main section, 1 = subsection, 2 = sub-subsection
  status: 'not_started' | 'draft' | 'edited' | 'approved' | 'generating'
  has_content: boolean
  version: number
  children?: SAPSection[]
}

// Scroll position tracking
interface ScrollState {
  protocol: number
  sapEditor: number
  selectedSectionId: string | null
}

// Drawer/overlay states
interface UIState {
  factDrawerOpen: boolean
  protocolOverlayOpen: boolean
  outlineCollapsed: boolean
  selectedFactId: string | null
}

// Teleport target for seamless context switching
interface TeleportTarget {
  sourceId: string | null // Legacy: Protocol page/section to scroll to
  sourceQuote: string | null // Verbatim text to search for and highlight
  sourceSection: string | null // Section number (for display only, NOT for search)
  searchText: string | null // Fallback search text (fact value/definition)
  sectionId: string | null // SAP section to focus
  timestamp: number
}

interface WorkspaceState {
  // Core identifiers
  workspaceId: string | null

  // View mode
  viewMode: ViewMode

  // Scroll positions (persisted)
  scroll: ScrollState

  // UI state
  ui: UIState

  // Teleport target for context switching
  teleportTarget: TeleportTarget | null

  // Extracted facts organized by category
  facts: ExtractionFact[]

  // SAP outline tree
  outline: SAPSection[]

  // Currently selected section
  selectedSectionId: string | null

  // Protocol metadata
  protocolPages: number

  // Actions
  setWorkspaceId: (id: string) => void
  setViewMode: (mode: ViewMode) => void

  // Scroll management
  setProtocolScroll: (position: number) => void
  setSapEditorScroll: (position: number) => void

  // UI toggles
  toggleFactDrawer: () => void
  openFactDrawer: () => void
  closeFactDrawer: () => void
  toggleProtocolOverlay: () => void
  openProtocolOverlay: () => void
  closeProtocolOverlay: () => void
  toggleOutline: () => void

  // Fact selection
  selectFact: (factId: string | null) => void

  // Section selection
  selectSection: (sectionId: string | null) => void

  // Data setters
  setFacts: (facts: ExtractionFact[]) => void
  updateFact: (factId: string, updates: Partial<ExtractionFact>) => void
  updateFactStatus: (factId: string, status: FactStatus, message?: string) => void
  setOutline: (outline: SAPSection[]) => void
  updateSectionStatus: (sectionId: string, status: SAPSection['status']) => void

  // Teleport actions
  teleportToProtocol: (sourceQuote: string | null, sourceSection: string | null, searchText?: string) => void
  teleportToSection: (sectionId: string) => void
  clearTeleport: () => void

  // Reset
  reset: () => void
}

const initialState = {
  workspaceId: null,
  viewMode: 'sap-authoring' as ViewMode,
  scroll: {
    protocol: 0,
    sapEditor: 0,
    selectedSectionId: null,
  },
  ui: {
    factDrawerOpen: false,
    protocolOverlayOpen: false,
    outlineCollapsed: false,
    selectedFactId: null,
  },
  teleportTarget: null,
  facts: [],
  outline: [],
  selectedSectionId: null,
  protocolPages: 0,
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      ...initialState,

      setWorkspaceId: (id) => set({ workspaceId: id }),

      setViewMode: (mode) => set({ viewMode: mode }),

      // Scroll management
      setProtocolScroll: (position) =>
        set((state) => ({
          scroll: { ...state.scroll, protocol: position },
        })),

      setSapEditorScroll: (position) =>
        set((state) => ({
          scroll: { ...state.scroll, sapEditor: position },
        })),

      // UI toggles
      toggleFactDrawer: () =>
        set((state) => ({
          ui: { ...state.ui, factDrawerOpen: !state.ui.factDrawerOpen },
        })),

      openFactDrawer: () =>
        set((state) => ({
          ui: { ...state.ui, factDrawerOpen: true },
        })),

      closeFactDrawer: () =>
        set((state) => ({
          ui: { ...state.ui, factDrawerOpen: false },
        })),

      toggleProtocolOverlay: () =>
        set((state) => ({
          ui: { ...state.ui, protocolOverlayOpen: !state.ui.protocolOverlayOpen },
        })),

      openProtocolOverlay: () =>
        set((state) => ({
          ui: { ...state.ui, protocolOverlayOpen: true },
        })),

      closeProtocolOverlay: () =>
        set((state) => ({
          ui: { ...state.ui, protocolOverlayOpen: false },
        })),

      toggleOutline: () =>
        set((state) => ({
          ui: { ...state.ui, outlineCollapsed: !state.ui.outlineCollapsed },
        })),

      // Fact selection
      selectFact: (factId) =>
        set((state) => ({
          ui: { ...state.ui, selectedFactId: factId },
        })),

      // Section selection
      selectSection: (sectionId) => set({ selectedSectionId: sectionId }),

      // Data setters
      setFacts: (facts) => set({ facts }),

      updateFact: (factId, updates) =>
        set((state) => ({
          facts: state.facts.map((f) =>
            f.id === factId ? { ...f, ...updates } : f
          ),
        })),

      updateFactStatus: (factId, status, message) =>
        set((state) => ({
          facts: state.facts.map((f) =>
            f.id === factId
              ? { ...f, status, warning_message: message }
              : f
          ),
        })),

      setOutline: (outline) => set({ outline }),

      updateSectionStatus: (sectionId, status) =>
        set((state) => ({
          outline: updateSectionInTree(state.outline, sectionId, { status }),
        })),

      // Teleport actions - for seamless context switching
      teleportToProtocol: (sourceQuote, sourceSection, searchText) =>
        set({
          viewMode: 'protocol-audit',
          teleportTarget: {
            sourceId: null,
            sourceQuote,
            sourceSection,
            searchText: searchText || null,
            sectionId: null,
            timestamp: Date.now(),
          },
        }),

      teleportToSection: (sectionId) =>
        set({
          viewMode: 'sap-authoring',
          selectedSectionId: sectionId,
          teleportTarget: {
            sourceId: null,
            sourceQuote: null,
            sourceSection: null,
            searchText: null,
            sectionId,
            timestamp: Date.now(),
          },
        }),

      clearTeleport: () => set({ teleportTarget: null }),

      reset: () => set(initialState),
    }),
    {
      name: 'workspace-storage',
      partialize: (state) => ({
        scroll: state.scroll,
        ui: {
          outlineCollapsed: state.ui.outlineCollapsed,
        },
      }),
    }
  )
)

// Helper to update a section in the nested tree
function updateSectionInTree(
  sections: SAPSection[],
  sectionId: string,
  updates: Partial<SAPSection>
): SAPSection[] {
  return sections.map((section) => {
    if (section.id === sectionId) {
      return { ...section, ...updates }
    }
    if (section.children) {
      return {
        ...section,
        children: updateSectionInTree(section.children, sectionId, updates),
      }
    }
    return section
  })
}

// Selectors for optimized re-renders
export const selectFlaggedFacts = (state: WorkspaceState) =>
  state.facts.filter((f) => f.status === 'flagged' || f.status === 'warning')

export const selectFactsByCategory = (state: WorkspaceState, category: string) =>
  state.facts.filter((f) => f.category === category)

export const selectFlatOutline = (state: WorkspaceState): SAPSection[] => {
  const flatten = (sections: SAPSection[]): SAPSection[] => {
    return sections.flatMap((s) => [s, ...(s.children ? flatten(s.children) : [])])
  }
  return flatten(state.outline)
}

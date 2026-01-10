/**
 * SAP Workbench TypeScript Models
 * Production-grade data models for Phase 2/3 oncology SAP authoring
 */

// ============================================================================
// STUDY & WORKSPACE
// ============================================================================

export type StudyPhase = 'Phase 1' | 'Phase 1/2' | 'Phase 2' | 'Phase 2/3' | 'Phase 3' | 'Phase 4'
export type TherapeuticArea = 'oncology' | 'cardiology' | 'neurology' | 'immunology' | 'infectious_disease' | 'rare_disease' | 'other'
export type ReviewStatus = 'draft' | 'in_review' | 'approved' | 'rejected'

export interface Study {
  id: string
  name: string
  protocol_id: string
  study_id: string
  phase: StudyPhase
  therapeutic_area: TherapeuticArea
  indication: string
  sponsor: string
  created_at: string
  updated_at: string
  owner: string
  protocol_version: string
  sap_version: string
  review_status: ReviewStatus
  progress: number // 0-100
  changes_pending: number
  sections_total: number
  sections_completed: number
  sections_approved: number
}

export interface Workspace {
  id: string
  name: string
  created_at: string
  updated_at: string
  phase: string
  therapeutic_area: string
  indication: string
  protocol_filename: string
  protocol_version: number
  sap_version: number
}

// ============================================================================
// PROTOCOL EXTRACTION
// ============================================================================

export interface ExtractedFact {
  id: string
  category: string
  name: string
  value: string
  confidence: number // 0-1
  citations: CitationRef[]
  status: 'confirmed' | 'uncertain' | 'flagged' | 'user_edited'
  user_notes?: string
}

export interface CitationRef {
  page: number
  section: string
  text: string
  start_char: number
  end_char: number
}

export interface Endpoint {
  id: string
  type: 'primary' | 'secondary' | 'exploratory'
  name: string
  definition: string
  measurement: string
  timepoint?: string
  analysis_method?: string
  estimand_strategy?: string
  citations: CitationRef[]
}

export interface Population {
  id: string
  name: string // ITT, mITT, Safety, PP, etc.
  definition: string
  inclusion_rules: string[]
  exclusion_rules: string[]
  citations: CitationRef[]
}

export interface TreatmentArm {
  id: string
  name: string
  description: string
  dose?: string
  schedule?: string
  n_planned?: number
}

export interface ProtocolMetadata {
  study_id: string
  study_title: string
  phase: string
  therapeutic_area: string
  indication: string
  disease_setting: string // adjuvant, neoadjuvant, metastatic, etc.
  performance_status_scale: string // ECOG, Karnofsky, ASA
  response_criteria: string // RECIST 1.1, iRECIST, Lugano, etc.
  geographic_countries: string[]
  endpoints: Endpoint[]
  populations: Population[]
  treatment_arms: TreatmentArm[]
  stratification_factors: string[]
  sample_size: number | null
  sample_size_per_arm: number | null
  prohibition_rules: string[]
  extraction_method: string
  confidence_score: number
}

// ============================================================================
// SAP SECTIONS
// ============================================================================

export type SectionStatus = 'not_started' | 'generating' | 'draft' | 'edited' | 'in_review' | 'approved'

export interface SAPSection {
  id: string
  name: string
  display_name: string
  order: number
  parent_id?: string
  status: SectionStatus
  has_content: boolean
  content: string
  version: number
  owner?: string
  last_updated?: string
  needs_update: boolean
  impacted_by_change: boolean
  protocol_excerpts_used: string[]
  metadata_used: string[]
  generated_at?: string
  approved_at?: string
  approved_by?: string
}

export interface SectionOutline {
  id: string
  name: string
  display_name: string
  status: SectionStatus
  has_content: boolean
  version: number
  children?: SectionOutline[]
  needs_update?: boolean
}

// ============================================================================
// PARAGRAPH-LEVEL PROVENANCE
// ============================================================================

export interface Paragraph {
  id: string
  section_id: string
  order: number
  content: string
  provenance: Provenance[]
  is_locked: boolean
  is_user_edited: boolean
  generated_version: number
  current_version: number
}

export interface Provenance {
  type: 'protocol_citation' | 'metadata_fact' | 'user_decision' | 'template' | 'regenerated'
  source_id: string
  source_text: string
  citation?: CitationRef
  timestamp: string
  user?: string
}

// ============================================================================
// ESTIMANDS (ICH E9 R1)
// ============================================================================

export type EstimandStrategy = 'treatment_policy' | 'hypothetical' | 'composite' | 'while_on_treatment' | 'principal_stratum'

export interface IntercurrentEvent {
  id: string
  name: string
  description: string
  strategy: EstimandStrategy
  handling_rule: string
}

export interface Estimand {
  id: string
  endpoint_id: string
  population_id: string
  treatment_comparison: string
  summary_measure: string
  intercurrent_events: IntercurrentEvent[]
}

// ============================================================================
// MULTIPLICITY & ALPHA STRATEGY
// ============================================================================

export interface HypothesisNode {
  id: string
  name: string
  endpoint_id: string
  alpha_allocation: number // fraction of alpha
  parent_id?: string
  children: string[]
  order: number
  is_gatekeeper: boolean
}

export interface MultiplicityStrategy {
  type: 'hierarchical' | 'gatekeeping' | 'fallback' | 'hochberg' | 'holm'
  hypotheses: HypothesisNode[]
  overall_alpha: number
  interim_alpha_spend?: number[]
}

// ============================================================================
// INTERIM ANALYSIS
// ============================================================================

export interface InterimAnalysis {
  id: string
  analysis_number: number
  information_fraction: number
  timing_description: string
  alpha_spent: number
  cumulative_alpha: number
  efficacy_boundary?: number
  futility_boundary?: number
  spending_function: 'obrien_fleming' | 'pocock' | 'hwang_shih_decani' | 'custom'
  allows_sample_size_reestimation: boolean
}

// ============================================================================
// CENSORING RULES (Time-to-Event)
// ============================================================================

export interface CensoringRule {
  id: string
  endpoint_id: string
  scenario: string
  event_date: string
  censoring_date: string
  is_event: boolean
  notes: string
}

export interface TimeToEventDefinition {
  endpoint_id: string
  endpoint_name: string
  event_definition: string
  censoring_rules: CensoringRule[]
  analysis_method: string // log-rank, Cox, etc.
  stratification_factors: string[]
}

// ============================================================================
// CHANGE IMPACT
// ============================================================================

export type ChangeSeverity = 'critical' | 'major' | 'minor' | 'informational'

export interface ProtocolChange {
  id: string
  change_type: string
  old_value: string
  new_value: string
  affected_sections: string[]
  severity: ChangeSeverity
  requires_rereview: boolean
}

export interface ChangeImpact {
  protocol_version_from: number
  protocol_version_to: number
  changes: ProtocolChange[]
  impacted_sections: {
    section_id: string
    section_name: string
    impact_description: string
    severity: ChangeSeverity
    requires_regeneration: boolean
    reviewed: boolean
    reviewed_by?: string
    reviewed_at?: string
  }[]
}

// ============================================================================
// REVIEW & APPROVAL
// ============================================================================

export interface ReviewComment {
  id: string
  section_id: string
  paragraph_id?: string
  content: string
  author: string
  created_at: string
  resolved: boolean
  resolved_by?: string
  resolved_at?: string
}

export interface SectionApproval {
  section_id: string
  status: 'pending' | 'approved' | 'rejected' | 'needs_revision'
  reviewer: string
  reviewed_at: string
  comments: string
  signature?: string
}

// ============================================================================
// AUDIT TRAIL
// ============================================================================

export type AuditEventType =
  | 'workspace_created'
  | 'protocol_uploaded'
  | 'protocol_updated'
  | 'metadata_extracted'
  | 'fact_confirmed'
  | 'fact_edited'
  | 'section_generated'
  | 'section_regenerated'
  | 'section_edited'
  | 'section_approved'
  | 'section_rejected'
  | 'comment_added'
  | 'comment_resolved'
  | 'sap_exported'
  | 'change_impact_reviewed'

export interface AuditEvent {
  id: string
  workspace_id: string
  event_type: AuditEventType
  timestamp: string
  user: string
  details: Record<string, any>
  section_id?: string
  old_value?: string
  new_value?: string
}

// ============================================================================
// API RESPONSE TYPES
// ============================================================================

export interface WorkspaceListResponse {
  workspaces: Workspace[]
}

export interface MetadataResponse extends ProtocolMetadata {
  // Additional fields from API
}

export interface OutlineResponse {
  sections: SectionOutline[]
}

export interface SectionContentResponse {
  id: string
  name: string
  display_name: string
  status: string
  content: string
  protocol_excerpts_used: string[]
  metadata_used: string[]
  version: number
}

export interface ExportResponse {
  content: string
  format: 'markdown' | 'docx' | 'pdf'
  filename: string
}

// ============================================================================
// UI STATE TYPES
// ============================================================================

export interface WorkspaceUIState {
  selectedSectionId: string | null
  isGenerating: boolean
  isEditing: boolean
  showProvenance: boolean
  showProtocol: boolean
  activeTab: 'editor' | 'structured' | 'preview'
  searchQuery: string
}

export interface SectionEditorState {
  content: string
  isDirty: boolean
  lastSaved: string | null
  history: { content: string; timestamp: string }[]
  historyIndex: number
}

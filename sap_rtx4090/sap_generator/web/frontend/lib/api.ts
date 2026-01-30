/**
 * SAP Workbench API Client
 * Handles all communication with the backend
 */

import type {
  Workspace,
  WorkspaceListResponse,
  MetadataResponse,
  OutlineResponse,
  SectionContentResponse,
  ExportResponse,
  AuditEvent,
} from './types'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ============================================================================
// API ERROR HANDLING
// ============================================================================

export class APIError extends Error {
  constructor(
    message: string,
    public status: number,
    public details?: any
  ) {
    super(message)
    this.name = 'APIError'
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}`
    try {
      const errorData = await response.json()
      errorMessage = errorData.detail || errorData.message || errorMessage
    } catch {
      // Ignore JSON parse error
    }
    throw new APIError(errorMessage, response.status)
  }
  return response.json()
}

// ============================================================================
// WORKSPACE MANAGEMENT
// ============================================================================

export async function listWorkspaces(): Promise<Workspace[]> {
  const response = await fetch(`${API_URL}/workbench/list`)
  const data = await handleResponse<WorkspaceListResponse>(response)
  return data.workspaces || []
}

export async function createWorkspace(
  protocolContent: string,
  protocolFilename: string,
  phase: string,
  therapeuticArea: string,
  indication: string
): Promise<Workspace> {
  const response = await fetch(`${API_URL}/workbench/create`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      protocol_content: protocolContent,
      protocol_filename: protocolFilename,
      phase,
      therapeutic_area: therapeuticArea,
      indication,
    }),
  })
  return handleResponse<Workspace>(response)
}

export async function uploadProtocol(
  file: File,
  phase: string,
  therapeuticArea: string,
  indication: string
): Promise<Workspace> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('phase', phase)
  formData.append('therapeutic_area', therapeuticArea)
  formData.append('indication', indication)

  const response = await fetch(`${API_URL}/workbench/upload`, {
    method: 'POST',
    body: formData,
  })
  return handleResponse<Workspace>(response)
}

// ============================================================================
// PROTOCOL METADATA
// ============================================================================

export async function getMetadata(workspaceId: string): Promise<MetadataResponse> {
  const response = await fetch(`${API_URL}/workbench/${workspaceId}/metadata`)
  return handleResponse<MetadataResponse>(response)
}

// ============================================================================
// SAP OUTLINE & SECTIONS
// ============================================================================

export async function getOutline(workspaceId: string): Promise<OutlineResponse> {
  const response = await fetch(`${API_URL}/workbench/${workspaceId}/outline`)
  return handleResponse<OutlineResponse>(response)
}

export async function generateSection(
  workspaceId: string,
  sectionId: string,
  regenerate: boolean = false
): Promise<SectionContentResponse> {
  const url = `${API_URL}/workbench/${workspaceId}/generate/${sectionId}${regenerate ? '?regenerate=true' : ''}`
  const response = await fetch(url, { method: 'POST' })
  return handleResponse<SectionContentResponse>(response)
}

export async function getSection(
  workspaceId: string,
  sectionId: string
): Promise<SectionContentResponse> {
  const response = await fetch(`${API_URL}/workbench/${workspaceId}/section/${sectionId}`)
  return handleResponse<SectionContentResponse>(response)
}

export async function updateSection(
  workspaceId: string,
  sectionId: string,
  content: string,
  comments?: string
): Promise<SectionContentResponse> {
  const response = await fetch(`${API_URL}/workbench/${workspaceId}/section/${sectionId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, comments: comments || '' }),
  })
  return handleResponse<SectionContentResponse>(response)
}

export async function approveSection(
  workspaceId: string,
  sectionId: string
): Promise<void> {
  const response = await fetch(`${API_URL}/workbench/${workspaceId}/section/${sectionId}/approve`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new APIError('Failed to approve section', response.status)
  }
}

// ============================================================================
// PROVENANCE & TRACEABILITY
// ============================================================================

export async function getProvenance(workspaceId: string): Promise<any> {
  const response = await fetch(`${API_URL}/workbench/${workspaceId}/provenance`)
  return handleResponse<any>(response)
}

// ============================================================================
// PROTOCOL UPDATES
// ============================================================================

export async function updateProtocol(
  workspaceId: string,
  newProtocolContent: string
): Promise<any> {
  const response = await fetch(`${API_URL}/workbench/${workspaceId}/update-protocol`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ protocol_content: newProtocolContent }),
  })
  return handleResponse<any>(response)
}

// ============================================================================
// EXPORT
// ============================================================================

export async function exportSAP(
  workspaceId: string,
  format: 'markdown' | 'docx' | 'pdf' = 'markdown'
): Promise<ExportResponse> {
  const response = await fetch(`${API_URL}/workbench/${workspaceId}/export?format=${format}`)
  return handleResponse<ExportResponse>(response)
}

// ============================================================================
// AUDIT TRAIL
// ============================================================================

export async function getAuditTrail(
  workspaceId: string,
  filters?: {
    event_type?: string
    user?: string
    from_date?: string
    to_date?: string
  }
): Promise<AuditEvent[]> {
  const params = new URLSearchParams()
  if (filters?.event_type) params.append('event_type', filters.event_type)
  if (filters?.user) params.append('user', filters.user)
  if (filters?.from_date) params.append('from_date', filters.from_date)
  if (filters?.to_date) params.append('to_date', filters.to_date)

  const queryString = params.toString()
  const url = `${API_URL}/workbench/${workspaceId}/audit${queryString ? `?${queryString}` : ''}`

  try {
    const response = await fetch(url)
    return handleResponse<AuditEvent[]>(response)
  } catch {
    // Audit trail endpoint may not exist yet
    return []
  }
}

// ============================================================================
// HEALTH CHECK
// ============================================================================

export async function healthCheck(): Promise<{ status: string; version?: string }> {
  const response = await fetch(`${API_URL}/health`)
  return handleResponse<{ status: string; version?: string }>(response)
}

// ============================================================================
// FULL SAP GENERATION (one-shot)
// ============================================================================

export interface GenerateJobResponse {
  job_id: string
  status: string
  message: string
}

export interface JobStatus {
  id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  generated_sap?: string
  quality_score?: number
  error_message?: string
  processing_time?: number
}

export async function generateFullSAP(
  protocolText: string,
  phase?: string,
  therapeuticArea?: string
): Promise<GenerateJobResponse> {
  const formData = new FormData()
  const blob = new Blob([protocolText], { type: 'text/plain' })
  formData.append('file', blob, 'protocol.txt')
  if (phase) formData.append('phase', phase)
  if (therapeuticArea) formData.append('therapeutic_area', therapeuticArea)

  const response = await fetch(`${API_URL}/upload`, {
    method: 'POST',
    body: formData,
  })
  return handleResponse<GenerateJobResponse>(response)
}

export async function getJobStatus(jobId: string): Promise<JobStatus> {
  const response = await fetch(`${API_URL}/status/${jobId}`)
  return handleResponse<JobStatus>(response)
}

export async function listJobs(): Promise<any[]> {
  const response = await fetch(`${API_URL}/jobs`)
  const data = await handleResponse<{ jobs: any[] }>(response)
  return data.jobs || []
}

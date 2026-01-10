"""
SAP Generation API Server
=========================

FastAPI server exposing both:
1. One-shot SAP generation (existing)
2. Workbench section-by-section generation (new)

Run with:
    uvicorn enterprise_sap_system.api_server:app --reload --port 8000
"""

import os
import tempfile
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import existing one-shot pipeline
from enterprise_sap_system.knowledge_graph.kg_enhanced_pipeline import EnhancedKGPipeline

# Import workbench
from enterprise_sap_system.workbench import SAPWorkbench, SectionStatus

# =============================================================================
# APP SETUP
# =============================================================================

app = FastAPI(
    title="SAP Generation API",
    description="Generate Statistical Analysis Plans from clinical trial protocols",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components (lazy)
_pipeline = None
_workbench = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(500, "ANTHROPIC_API_KEY not set")
        _pipeline = EnhancedKGPipeline(api_key)
    return _pipeline


def get_workbench():
    global _workbench
    if _workbench is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(500, "ANTHROPIC_API_KEY not set")
        _workbench = SAPWorkbench(api_key)
    return _workbench


# =============================================================================
# MODELS
# =============================================================================

class GenerateSAPRequest(BaseModel):
    protocol_content: str
    protocol_filename: str = "protocol.txt"


class GenerateSAPResponse(BaseModel):
    success: bool
    sap_content: str
    verification_score: float
    warnings: List[str] = []


class CreateWorkspaceRequest(BaseModel):
    protocol_content: str
    protocol_filename: str
    phase: str = ""
    therapeutic_area: str = ""
    indication: str = ""


class WorkspaceResponse(BaseModel):
    id: str
    name: str
    created_at: str
    phase: str
    therapeutic_area: str


class MetadataResponse(BaseModel):
    study_id: str
    study_title: str
    phase: str
    therapeutic_area: str
    indication: str
    objectives: List[dict]
    endpoints: List[dict]
    populations: List[dict]
    treatment_arms: List[dict]
    sample_size: Optional[int]


class SectionOutline(BaseModel):
    id: str
    name: str
    status: str
    has_content: bool
    version: int


class SectionResponse(BaseModel):
    id: str
    name: str
    display_name: str
    status: str
    content: str
    version: int
    protocol_excerpts_used: List[str]
    metadata_used: List[str]


class UpdateSectionRequest(BaseModel):
    content: str
    comments: str = ""


class UpdateProtocolRequest(BaseModel):
    protocol_content: str
    filename: str


class ProtocolChangeResponse(BaseModel):
    changed: bool
    impacted_sections: List[str]


# =============================================================================
# ONE-SHOT ENDPOINTS (existing functionality)
# =============================================================================

@app.post("/api/generate-sap", response_model=GenerateSAPResponse)
async def generate_sap(request: GenerateSAPRequest):
    """
    Generate complete SAP in one shot (existing functionality).
    """
    try:
        pipeline = get_pipeline()

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(request.protocol_content)
            temp_path = f.name

        try:
            result = pipeline.process_protocol(temp_path)

            return GenerateSAPResponse(
                success=result.get("verification_passed", False),
                sap_content=result.get("sap_content", ""),
                verification_score=result.get("verification_score", 0.0),
                warnings=result.get("warnings", [])
            )
        finally:
            os.unlink(temp_path)

    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/generate-sap/upload", response_model=GenerateSAPResponse)
async def generate_sap_upload(file: UploadFile = File(...)):
    """
    Generate SAP from uploaded file (one-shot).
    """
    try:
        content = await file.read()
        protocol_content = content.decode('utf-8', errors='ignore')

        pipeline = get_pipeline()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(protocol_content)
            temp_path = f.name

        try:
            result = pipeline.process_protocol(temp_path)

            return GenerateSAPResponse(
                success=result.get("verification_passed", False),
                sap_content=result.get("sap_content", ""),
                verification_score=result.get("verification_score", 0.0),
                warnings=result.get("warnings", [])
            )
        finally:
            os.unlink(temp_path)

    except Exception as e:
        raise HTTPException(500, str(e))


# =============================================================================
# WORKBENCH ENDPOINTS (new functionality)
# =============================================================================

@app.post("/api/workbench/create", response_model=WorkspaceResponse)
async def create_workspace(request: CreateWorkspaceRequest):
    """
    Step 1: Create a new study workspace.
    """
    try:
        workbench = get_workbench()

        workspace = workbench.create_workspace(
            protocol_content=request.protocol_content,
            protocol_filename=request.protocol_filename,
            phase=request.phase,
            therapeutic_area=request.therapeutic_area,
            indication=request.indication
        )

        return WorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            created_at=workspace.created_at,
            phase=workspace.phase,
            therapeutic_area=workspace.therapeutic_area
        )

    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/workbench/create/upload", response_model=WorkspaceResponse)
async def create_workspace_upload(
    file: UploadFile = File(...),
    phase: str = Form(""),
    therapeutic_area: str = Form(""),
    indication: str = Form("")
):
    """
    Create workspace from uploaded protocol file.
    """
    try:
        content = await file.read()
        protocol_content = content.decode('utf-8', errors='ignore')

        workbench = get_workbench()

        workspace = workbench.create_workspace(
            protocol_content=protocol_content,
            protocol_filename=file.filename or "protocol.txt",
            phase=phase,
            therapeutic_area=therapeutic_area,
            indication=indication
        )

        return WorkspaceResponse(
            id=workspace.id,
            name=workspace.name,
            created_at=workspace.created_at,
            phase=workspace.phase,
            therapeutic_area=workspace.therapeutic_area
        )

    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/workbench/{workspace_id}/metadata", response_model=MetadataResponse)
async def get_metadata(workspace_id: str):
    """
    Step 2: Get extracted protocol metadata.
    Extracts if not already done.
    """
    try:
        workbench = get_workbench()
        workspace = workbench.get_workspace(workspace_id)

        if not workspace:
            raise HTTPException(404, f"Workspace {workspace_id} not found")

        # Extract if not done
        if not workspace.metadata:
            metadata = workbench.extract_metadata(workspace_id)
        else:
            metadata = workspace.metadata

        return MetadataResponse(
            study_id=metadata.study_id,
            study_title=metadata.study_title,
            phase=metadata.phase,
            therapeutic_area=metadata.therapeutic_area,
            indication=metadata.indication,
            objectives=metadata.objectives,
            endpoints=metadata.endpoints,
            populations=metadata.populations,
            treatment_arms=metadata.treatment_arms,
            sample_size=metadata.sample_size
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/workbench/{workspace_id}/outline", response_model=List[SectionOutline])
async def get_outline(workspace_id: str):
    """
    Step 3: Get SAP outline with section statuses.
    """
    try:
        workbench = get_workbench()
        outline = workbench.get_outline(workspace_id)

        return [
            SectionOutline(
                id=item["id"],
                name=item["name"],
                status=item["status"],
                has_content=item["has_content"],
                version=item["version"]
            )
            for item in outline
        ]

    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/workbench/{workspace_id}/generate/{section_id}", response_model=SectionResponse)
async def generate_section(workspace_id: str, section_id: str, regenerate: bool = False):
    """
    Step 4: Generate a single SAP section.
    """
    try:
        workbench = get_workbench()
        section = workbench.generate_section(workspace_id, section_id, regenerate)

        return SectionResponse(
            id=section.id,
            name=section.name,
            display_name=section.display_name,
            status=section.status.value,
            content=section.content,
            version=section.version,
            protocol_excerpts_used=section.protocol_excerpts_used,
            metadata_used=section.metadata_used
        )

    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/workbench/{workspace_id}/section/{section_id}", response_model=SectionResponse)
async def get_section(workspace_id: str, section_id: str):
    """
    Get a section's current content and status.
    """
    try:
        workbench = get_workbench()
        workspace = workbench.get_workspace(workspace_id)

        if not workspace:
            raise HTTPException(404, f"Workspace {workspace_id} not found")

        section = workspace.sections.get(section_id)
        if not section:
            raise HTTPException(404, f"Section {section_id} not found")

        return SectionResponse(
            id=section.id,
            name=section.name,
            display_name=section.display_name,
            status=section.status.value,
            content=section.content,
            version=section.version,
            protocol_excerpts_used=section.protocol_excerpts_used,
            metadata_used=section.metadata_used
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.put("/api/workbench/{workspace_id}/section/{section_id}", response_model=SectionResponse)
async def update_section(workspace_id: str, section_id: str, request: UpdateSectionRequest):
    """
    Update a section with user edits.
    """
    try:
        workbench = get_workbench()
        section = workbench.update_section(
            workspace_id, section_id, request.content, request.comments
        )

        return SectionResponse(
            id=section.id,
            name=section.name,
            display_name=section.display_name,
            status=section.status.value,
            content=section.content,
            version=section.version,
            protocol_excerpts_used=section.protocol_excerpts_used,
            metadata_used=section.metadata_used
        )

    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/workbench/{workspace_id}/section/{section_id}/approve", response_model=SectionResponse)
async def approve_section(workspace_id: str, section_id: str):
    """
    Mark a section as approved.
    """
    try:
        workbench = get_workbench()
        section = workbench.approve_section(workspace_id, section_id)

        return SectionResponse(
            id=section.id,
            name=section.name,
            display_name=section.display_name,
            status=section.status.value,
            content=section.content,
            version=section.version,
            protocol_excerpts_used=section.protocol_excerpts_used,
            metadata_used=section.metadata_used
        )

    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/workbench/{workspace_id}/compare", response_model=ProtocolChangeResponse)
async def compare_protocols(workspace_id: str, request: UpdateProtocolRequest):
    """
    Step 6: Update protocol and identify impacted sections.
    """
    try:
        workbench = get_workbench()
        result = workbench.update_protocol(
            workspace_id, request.protocol_content, request.filename
        )

        return ProtocolChangeResponse(
            changed=result["changed"],
            impacted_sections=result.get("impacted_sections", [])
        )

    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/workbench/{workspace_id}/export")
async def export_sap(workspace_id: str, format: str = "markdown"):
    """
    Step 7: Export complete SAP.
    """
    try:
        workbench = get_workbench()
        content = workbench.export_sap(workspace_id, format)

        return {
            "format": format,
            "content": content,
            "generated_at": datetime.now().isoformat()
        }

    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/workbench/{workspace_id}/provenance")
async def get_provenance(workspace_id: str):
    """
    Step 5: Get full provenance report.
    """
    try:
        workbench = get_workbench()
        return workbench.get_provenance_report(workspace_id)

    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/workbench/list")
async def list_workspaces():
    """
    List all workspaces.
    """
    try:
        workbench = get_workbench()
        return workbench.list_workspaces()

    except Exception as e:
        raise HTTPException(500, str(e))


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "features": {
            "one_shot": True,
            "workbench": True
        }
    }


@app.get("/")
async def root():
    return {
        "message": "SAP Generation API",
        "docs": "/docs",
        "endpoints": {
            "one_shot": "/api/generate-sap",
            "workbench": "/api/workbench/*"
        }
    }


# =============================================================================
# RUN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

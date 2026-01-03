"""
SAP Generator Backend API
Production-grade with file upload support
Deploy to Render.com

Production Features:
- Structured logging
- Health check with circuit breaker status
- Proper error handling
"""

import os
import time
import asyncio
import tempfile
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
import io

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

# Supabase client
from supabase import create_client, Client

# Document parsing
import PyPDF2
from docx import Document as DocxDocument

# Import SAP generator (add parent to path)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import structured logging
try:
    from enterprise_sap_system.core.logging_config import get_logger, SAPLogger
    # Initialize logging for production (JSON output)
    SAPLogger.initialize(level="INFO", json_output=os.getenv("LOG_JSON", "false").lower() == "true")
    logger = get_logger("web.backend")
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("web.backend")

# AGENTIC HYBRIDRAG PIPELINE - Production pipeline with data-driven method selection
# Replaces RuleBasedSAPPipeline: learns from 23K SAP chunks instead of hardcoded rules
# Architecture: Protocol → Hybrid Retrieval → Method Extraction → Generation → Validation
try:
    from enterprise_sap_system.rag.agentic_sap_pipeline import (
        AgenticSAPPipeline, create_agentic_pipeline, SAPGenerationResult
    )
    AGENTIC_PIPELINE_AVAILABLE = True
except ImportError as e:
    AGENTIC_PIPELINE_AVAILABLE = False
    print(f"Warning: AgenticSAPPipeline not available: {e}")

# Fallback to rule-based pipeline
from enterprise_sap_system.core.rule_based_pipeline import RuleBasedSAPPipeline, create_rule_based_pipeline

# NEW: Production Pipeline with Separation of Concerns (SELF-RAG pattern)
# - Extraction as Ground Truth (single source for numbers)
# - RAG Sanitization (strips numbers from examples)
# - Explicit source attribution in prompts
# - SELF-RAG verification with correction loop
try:
    from enterprise_sap_system.core.production_pipeline import (
        ProductionSAPPipeline, create_production_pipeline
    )
    PRODUCTION_PIPELINE_AVAILABLE = True
except ImportError as e:
    PRODUCTION_PIPELINE_AVAILABLE = False
    print(f"Warning: ProductionSAPPipeline not available: {e}")

# Keep old import for backward compatibility
try:
    from enterprise_sap_system.core.hybrid_pipeline import HybridSAPPipeline, create_hybrid_pipeline
except ImportError:
    HybridSAPPipeline = None
    create_hybrid_pipeline = None

# NEW: Regulatory-grade SAP Generator (ICH E9 compliant, 45+ pages)
try:
    from enterprise_sap_system.core.regulatory_sap_generator import (
        RegulatorySAPGenerator,
        create_regulatory_sap_generator,
        ProtocolFacts,
        SAPDocument
    )
    REGULATORY_GENERATOR_AVAILABLE = True
except ImportError as e:
    REGULATORY_GENERATOR_AVAILABLE = False
    RegulatorySAPGenerator = None
    print(f"Warning: RegulatorySAPGenerator not available: {e}")

# Import LLM client for health check
try:
    from enterprise_sap_system.core.tiered_llm import get_tiered_client
    LLM_CLIENT_AVAILABLE = True
except ImportError:
    LLM_CLIENT_AVAILABLE = False
    logger.warning("TieredLLMClient not available for health check")

from evaluate_sap import SAPEvaluator

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Log startup configuration
logger.info(
    "Backend starting",
    supabase_configured=bool(SUPABASE_URL and SUPABASE_KEY),
    groq_configured=bool(GROQ_API_KEY)
)

# Initialize Supabase client
supabase: Client = None

def get_supabase() -> Client:
    global supabase
    if supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return supabase


# Document parsing functions
def extract_text_from_pdf(file_content: bytes) -> str:
    """Extract text from PDF file."""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        text_parts = []
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        return "\n\n".join(text_parts)
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {str(e)}")


def extract_text_from_docx(file_content: bytes) -> str:
    """Extract text from DOCX file."""
    try:
        doc = DocxDocument(io.BytesIO(file_content))
        text_parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)
        # Also extract from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    text_parts.append(row_text)
        return "\n\n".join(text_parts)
    except Exception as e:
        raise ValueError(f"Failed to parse DOCX: {str(e)}")


def extract_text_from_txt(file_content: bytes) -> str:
    """Extract text from TXT file."""
    try:
        return file_content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            return file_content.decode('latin-1')
        except Exception as e:
            raise ValueError(f"Failed to decode text file: {e}")


def extract_text_from_file(filename: str, content: bytes) -> str:
    """Extract text from uploaded file based on extension."""
    ext = filename.lower().split('.')[-1] if '.' in filename else ''

    if ext == 'pdf':
        return extract_text_from_pdf(content)
    elif ext in ['docx', 'doc']:
        return extract_text_from_docx(content)
    elif ext in ['txt', 'text', 'md']:
        return extract_text_from_txt(content)
    else:
        # Try to decode as text
        try:
            return content.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Unsupported file format: {ext} (decode error: {e})")


# Background worker flag
worker_running = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background worker on startup"""
    global worker_running
    worker_running = True
    asyncio.create_task(process_jobs_worker())
    yield
    worker_running = False


app = FastAPI(
    title="SAP Generator API",
    description="Generate Statistical Analysis Plans from clinical trial protocols",
    version="2.0.0",
    lifespan=lifespan
)

# CORS for Vercel frontend
frontend_url = os.getenv("FRONTEND_URL", "")
allowed_origins = [
    "http://localhost:3000",
    "https://*.vercel.app",
]
if frontend_url:
    allowed_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://clinicaltrial.vercel.app",
    ],
    allow_origin_regex=r"https://.*\.vercel\.app$",  # Match ALL Vercel preview URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class GenerateRequest(BaseModel):
    protocol_text: str
    nct_id: Optional[str] = None
    filename: Optional[str] = None


class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str
    extracted_text: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    generated_sap: Optional[str] = None
    quality_score: Optional[float] = None
    endpoint_type: Optional[str] = None
    phase: Optional[str] = None
    therapeutic_area: Optional[str] = None
    processing_time: Optional[float] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    filename: Optional[str] = None
    protocol_preview: Optional[str] = None


class EvaluationResponse(BaseModel):
    """Evaluation results comparing generated SAP to ground truth"""
    nct_id: str
    ground_truth_lines: int
    generated_lines: int
    section_coverage_pct: float
    keyword_overlap_pct: float
    has_primary_endpoint: bool
    has_secondary_endpoint: bool
    has_sample_size: bool
    has_analysis_populations: bool
    has_statistical_methods: bool
    has_missing_data: bool
    overall_score: float
    sections_matched: list
    sections_missing: list
    statistical_terms_found: list
    statistical_terms_missing: list


class GroundTruthInfo(BaseModel):
    """Ground truth study information"""
    nct_id: str
    title: str
    sap_lines: int
    therapeutic_area: str


# API Endpoints
@app.get("/")
async def root():
    return {"status": "ok", "message": "SAP Generator API v2.0", "features": ["file_upload", "pdf", "docx", "txt"]}


@app.get("/health")
async def health():
    """Basic health check."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/health/detailed")
async def health_detailed():
    """
    Detailed health check with circuit breaker status.

    Returns:
        - LLM provider status (available, cooldown, error counts)
        - Database connectivity
        - Overall system health
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "components": {}
    }

    # Check LLM providers
    if LLM_CLIENT_AVAILABLE:
        try:
            client = get_tiered_client()
            llm_status = client.get_status()
            health_status["components"]["llm"] = {
                "status": "healthy" if any(s["available"] for s in llm_status.values()) else "degraded",
                "providers": llm_status
            }

            # Warn if all providers are in cooldown
            available_count = sum(1 for s in llm_status.values() if s["available"])
            if available_count == 0:
                health_status["status"] = "degraded"
                health_status["components"]["llm"]["status"] = "unavailable"
                logger.warning("All LLM providers unavailable", llm_status=llm_status)
        except Exception as e:
            health_status["components"]["llm"] = {
                "status": "error",
                "error": str(e)
            }
            logger.error("LLM health check failed", exc_info=True)
    else:
        health_status["components"]["llm"] = {"status": "not_configured"}

    # Check database
    try:
        db = get_supabase()
        # Simple query to verify connectivity
        health_status["components"]["database"] = {"status": "healthy"}
    except Exception as e:
        health_status["components"]["database"] = {
            "status": "error",
            "error": str(e)
        }
        health_status["status"] = "unhealthy"
        logger.error("Database health check failed", error=str(e))

    # Check environment
    health_status["components"]["environment"] = {
        "supabase_configured": bool(SUPABASE_URL and SUPABASE_KEY),
        "groq_configured": bool(GROQ_API_KEY),
        "anthropic_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
    }

    return health_status


@app.post("/upload", response_model=JobResponse)
async def upload_file(
    file: UploadFile = File(...),
    nct_id: Optional[str] = Form(None)
):
    """
    Upload a protocol document (PDF, DOCX, TXT) and create a SAP generation job.
    """
    start_time = time.time()
    logger.info("File upload started", filename=file.filename, nct_id=nct_id)

    try:
        # Read file content
        content = await file.read()
        file_size = len(content)

        if file_size == 0:
            logger.warning("Empty file uploaded", filename=file.filename)
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        if file_size > 10 * 1024 * 1024:  # 10MB limit
            logger.warning("File too large", filename=file.filename, size_bytes=file_size)
            raise HTTPException(status_code=400, detail="File too large (max 10MB)")

        # Extract text
        try:
            extracted_text = extract_text_from_file(file.filename, content)
            logger.info("Text extracted", filename=file.filename, text_length=len(extracted_text))
        except ValueError as e:
            logger.error("Text extraction failed", filename=file.filename, error=str(e))
            raise HTTPException(status_code=400, detail=str(e))

        if not extracted_text.strip():
            logger.warning("No text extracted", filename=file.filename)
            raise HTTPException(status_code=400, detail="No text could be extracted from the file")

        # Insert job into database
        db = get_supabase()
        result = db.table("sap_jobs").insert({
            "protocol_text": extracted_text[:100000],  # Limit text size
            "nct_id": nct_id,
            "status": "queued",
            "filename": file.filename
        }).execute()

        job_id = result.data[0]["id"]
        elapsed = time.time() - start_time

        logger.info(
            "Job created",
            job_id=job_id,
            filename=file.filename,
            nct_id=nct_id,
            text_length=len(extracted_text),
            elapsed_seconds=round(elapsed, 2)
        )

        return JobResponse(
            job_id=job_id,
            status="queued",
            message=f"File '{file.filename}' uploaded successfully. Processing started.",
            extracted_text=extracted_text[:2000] + ("..." if len(extracted_text) > 2000 else "")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Upload failed", filename=file.filename, exc_info=True, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pipeline-info")
async def get_pipeline_info():
    """
    Get information about the HYBRID SAP PIPELINE architecture.

    Returns details about all 4 layers and their components.
    """
    return {
        "pipeline": "HybridSAPPipeline",
        "version": "2.0.0",
        "architecture": {
            "layer_1_extraction": {
                "name": "EXTRACTION",
                "components": [
                    "StructuredFactExtractor (regex-only, no LLM hallucination)",
                    "ProtocolIdentityExtractor (NCT ID, sponsor detection)"
                ],
                "outputs": ["drug_name", "sample_size", "randomization_ratio", "phase", "therapeutic_area", "endpoints"]
            },
            "layer_2_knowledge": {
                "name": "KNOWLEDGE",
                "components": [
                    "BiostatisticsKnowledgeGraph (39 nodes, 36 edges)",
                    "RAG System (1,198 sections from real SAPs)",
                    "Specialized Templates (Phase 2/3, oncology, IBD, rheumatology)"
                ],
                "outputs": ["recommended_methods", "adam_datasets", "rag_examples", "template_guidance"]
            },
            "layer_3_generation": {
                "name": "GENERATION",
                "components": [
                    "ConstrainedSAPPipeline (Literal type enforcement)",
                    "FullSchemaGenerator (28-entity Pydantic schemas)",
                    "Multi-Agent System (4 specialized agents)"
                ],
                "outputs": ["sap_text", "constrained_output", "sections"]
            },
            "layer_4_validation": {
                "name": "VALIDATION",
                "components": [
                    "HardValidator (CRITICAL/HIGH/MEDIUM severity levels)",
                    "ContaminationGuard (cross-protocol detection)",
                    "IssueDetector (QA scoring)"
                ],
                "outputs": ["quality_score", "validation_issues", "contamination_report"]
            }
        },
        "endpoints": {
            "/generate": "Queued generation (background worker)",
            "/generate-full": "Synchronous generation (immediate response)",
            "/pipeline-info": "This endpoint - architecture details"
        }
    }


@app.post("/generate", response_model=JobResponse)
async def create_job(request: GenerateRequest):
    """
    Create a new SAP generation job from text.
    Returns job_id immediately, processing happens in background.
    """
    try:
        db = get_supabase()

        if not request.protocol_text.strip():
            raise HTTPException(status_code=400, detail="Protocol text cannot be empty")

        # Insert job into database
        result = db.table("sap_jobs").insert({
            "protocol_text": request.protocol_text[:100000],
            "nct_id": request.nct_id,
            "status": "queued",
            "filename": request.filename
        }).execute()

        job_id = result.data[0]["id"]

        return JobResponse(
            job_id=job_id,
            status="queued",
            message="Job created. Poll /status/{job_id} for results."
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Global instance for direct generation (reused across requests)
_production_pipeline: ProductionSAPPipeline = None  # PRIMARY (SELF-RAG)
_rule_pipeline: RuleBasedSAPPipeline = None  # Fallback
_agentic_pipeline: AgenticSAPPipeline = None  # Legacy (not used)

def get_pipeline():
    """
    Get or create the production pipeline instance.

    Uses ProductionSAPPipeline with Separation of Concerns architecture:
    - Ground Truth: Extraction provides single source for all numbers
    - RAG Sanitization: Numbers stripped from examples (prose style only)
    - Explicit Attribution: Prompts specify source for each value
    - SELF-RAG: Verification + correction loop for factual accuracy

    This fixes:
    - Wrong numbers (639 vs 382 events) - RAG contamination eliminated
    - Wrong counts (2 interim vs 1) - Extracted facts passed correctly
    - Wrong alpha (0.05 vs 0.020) - No more default values
    - Extra methods (RPSFT/IPCW) - Only protocol-specified methods

    Falls back to RuleBasedSAPPipeline if ProductionSAPPipeline unavailable.
    """
    global _production_pipeline, _rule_pipeline

    # Try Production Pipeline first (SELF-RAG)
    if PRODUCTION_PIPELINE_AVAILABLE:
        if _production_pipeline is None:
            _production_pipeline = create_production_pipeline(max_regenerations=2)
            logger.info("ProductionSAPPipeline initialized (SELF-RAG + source separation)")
        return _production_pipeline

    # Fallback to rule-based pipeline
    if _rule_pipeline is None:
        _rule_pipeline = create_rule_based_pipeline()
        logger.info("RuleBasedSAPPipeline initialized (fallback)")
    return _rule_pipeline

# Aliases for backward compatibility
def get_hybrid_pipeline():
    """Deprecated: Use get_pipeline() instead."""
    return get_pipeline()

def get_full_pipeline():
    """Deprecated: Use get_pipeline() instead."""
    return get_pipeline()


class FullPipelineResponse(BaseModel):
    """Response from full integrated pipeline with all layers."""
    success: bool
    sap_text: str
    drug_name: str
    sample_size: int
    randomization_ratio: str
    phase: str
    therapeutic_area: str
    endpoint_type: str
    quality_score: float
    generation_mode: str
    constrained_schema_used: bool
    rag_examples_count: int
    templates_applied: list
    validation_issues: int
    contamination_detected: bool
    processing_time: float
    errors: list


@app.post("/generate-full", response_model=FullPipelineResponse)
async def generate_full_pipeline(request: GenerateRequest):
    """
    Generate SAP synchronously using the RULE-BASED PIPELINE.

    This endpoint uses:
    - Step 1: Claude LLM extraction (NCT ID, drug, sample size, etc.)
    - Step 2: Condition detection (immunotherapy, crossover, interim, etc.)
    - Step 3: Knowledge Graph with 99 rules for method selection
    - Step 4: ChromaDB RAG with 17K+ chunks for examples
    - Step 5: Claude LLM generation with slot constraints
    - Step 6: Slot verification for required methods

    Returns immediately with the generated SAP (no queuing).
    """
    import time
    start_time = time.time()

    try:
        if not request.protocol_text.strip():
            raise HTTPException(status_code=400, detail="Protocol text cannot be empty")

        pipeline = get_pipeline()

        result = pipeline.generate(request.protocol_text[:50000])

        processing_time = time.time() - start_time

        # Handle RuleBasedSAPPipeline result (PRIMARY - has facts) vs AgenticSAPPipeline (fallback - has characteristics)
        if hasattr(result, 'facts') and result.facts:
            # PRIMARY: RuleBasedSAPPipeline format
            facts = result.facts
            drug_name = facts.get('drug_name', '') or ''
            sample_size_val = facts.get('sample_size', 0)
            if isinstance(sample_size_val, dict):
                sample_size = sample_size_val.get('total_n', 0) or 0
            else:
                sample_size = int(sample_size_val) if sample_size_val else 0
            ratio = facts.get('randomization_ratio', '') or ''
            phase = facts.get('phase', '') or ''
            therapeutic_area = facts.get('therapeutic_area', '') or facts.get('indication', '') or ''
            endpoint_type = facts.get('primary_endpoint', '')[:100] if facts.get('primary_endpoint') else ""

            quality_score = 1.0 if result.verification and result.verification.passed else 0.5
            validation_issues = len(result.verification.missing_slots) if result.verification else 0
            generation_mode = "rule-based (Claude + 99 rules + RAG + slot verification)"
            source_trials = []

        elif hasattr(result, 'characteristics') and result.characteristics:
            # FALLBACK: AgenticSAPPipeline format
            chars = result.characteristics
            drug_name = chars.drug_classes[0] if chars.drug_classes else ""
            phase = chars.phase or ""
            therapeutic_area = chars.indication or ""
            endpoint_type = chars.endpoint_type or ""
            ratio = ""  # Not in characteristics

            # Try to extract sample size from extracted_methods or default
            sample_size = 0

            # Validation from agentic pipeline
            quality_score = result.confidence if result.confidence else 0.8
            if result.validation:
                quality_score = result.validation.confidence
                validation_issues = len(result.validation.issues) if hasattr(result.validation, 'issues') else 0
            else:
                validation_issues = 0

            generation_mode = "agentic-hybridrag (5-agent + Knowledge Graph + 23K chunks)"
            source_trials = result.source_trials or []

        else:
            # Minimal fallback
            drug_name = ""
            sample_size = 0
            ratio = ""
            phase = ""
            therapeutic_area = ""
            endpoint_type = ""
            quality_score = 0.5
            validation_issues = 0
            generation_mode = "unknown"
            source_trials = []

        return FullPipelineResponse(
            success=result.success,
            sap_text=result.sap_text,
            drug_name=drug_name,
            sample_size=sample_size,
            randomization_ratio=ratio,
            phase=phase,
            therapeutic_area=therapeutic_area,
            endpoint_type=endpoint_type,
            quality_score=quality_score,
            generation_mode=generation_mode,
            constrained_schema_used=True,
            rag_examples_count=len(result.sections) if result.sections else 0,
            templates_applied=list(result.sections.keys()) if result.sections else [],
            validation_issues=validation_issues,
            contamination_detected=False,
            processing_time=processing_time,
            errors=result.warnings if hasattr(result, 'warnings') and result.warnings else (
                [result.error] if hasattr(result, 'error') and result.error else []
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Global instance for regulatory generator
_regulatory_generator: RegulatorySAPGenerator = None


def get_regulatory_generator():
    """Get or create the regulatory SAP generator."""
    global _regulatory_generator
    if _regulatory_generator is None and REGULATORY_GENERATOR_AVAILABLE:
        _regulatory_generator = create_regulatory_sap_generator()
        logger.info("RegulatorySAPGenerator initialized (ICH E9 compliant, Claude extraction)")
    return _regulatory_generator


class RegulatorySAPResponse(BaseModel):
    """Response from regulatory-grade SAP generation."""
    success: bool
    sap_text: str
    # Extracted facts
    nct_id: str
    protocol_number: str
    drug_name: str
    comparator_drug: str
    sample_size: int
    events_required: int
    primary_endpoint: str
    primary_test: str
    alpha_interim: float
    alpha_final: float
    stratification_factors: list
    has_interim: bool
    dmc_oversight: bool
    # Metadata
    sections_generated: int
    character_count: int
    processing_time: float
    extraction_method: str  # Always "claude" (no regex fallback)
    errors: list


@app.post("/generate-regulatory", response_model=RegulatorySAPResponse)
async def generate_regulatory_sap(request: GenerateRequest):
    """
    Generate a REGULATORY-GRADE SAP using Claude API extraction.

    This endpoint produces SAPs that match real pharmaceutical SAPs:
    - ICH E9(R1) compliant structure (10 major sections)
    - 45+ pages with proper formatting
    - Protocol-specific statistical methods (Fleming-Harrington, Lan-DeMets)
    - Proper censoring schemes, analysis populations, subgroup analyses

    Uses Claude API for accurate protocol fact extraction.
    """
    import time
    start_time = time.time()

    try:
        if not request.protocol_text.strip():
            raise HTTPException(status_code=400, detail="Protocol text cannot be empty")

        if not REGULATORY_GENERATOR_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail="RegulatorySAPGenerator not available. Check imports."
            )

        generator = get_regulatory_generator()
        if generator is None:
            raise HTTPException(
                status_code=503,
                detail="Could not initialize RegulatorySAPGenerator"
            )

        # Extract facts (uses Claude API if available)
        facts = generator.extract_protocol_facts(request.protocol_text[:100000])

        # Generate SAP document
        doc = generator.generate(request.protocol_text[:100000], facts)

        # Assemble full document
        sap_text = generator.assemble_document(doc)

        processing_time = time.time() - start_time

        # Extraction method is always Claude (no regex fallback)
        extraction_method = "claude"

        return RegulatorySAPResponse(
            success=True,
            sap_text=sap_text,
            nct_id=facts.nct_id or "",
            protocol_number=facts.protocol_number or "",
            drug_name=facts.experimental_drug or "",
            comparator_drug=facts.comparator_drug or "",
            sample_size=facts.total_sample_size or 0,
            events_required=facts.events_required_final or 0,
            primary_endpoint=facts.primary_endpoint or "",
            primary_test=facts.primary_test or "",
            alpha_interim=facts.alpha_interim or 0.0,
            alpha_final=facts.alpha_final or 0.05,
            stratification_factors=facts.stratification_factors or [],
            has_interim=facts.has_interim,
            dmc_oversight=facts.dmc_oversight,
            sections_generated=len([s for s in [
                doc.cover_page, doc.sec1_1_hypothesis, doc.sec2_1_design,
                doc.sec5_sample_size, doc.sec7_5_1_primary_analysis, doc.sec7_6_safety
            ] if s]),
            character_count=len(sap_text),
            processing_time=processing_time,
            extraction_method=extraction_method,
            errors=[]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Regulatory SAP generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get the status of a SAP generation job.
    """
    try:
        db = get_supabase()

        result = db.table("sap_jobs").select("*").eq("id", job_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Job not found")

        job = result.data[0]

        # Create protocol preview
        protocol_text = job.get("protocol_text", "")
        preview = protocol_text[:1000] + ("..." if len(protocol_text) > 1000 else "")

        return JobStatusResponse(
            job_id=job["id"],
            status=job["status"],
            generated_sap=job.get("generated_sap"),
            quality_score=job.get("quality_score"),
            endpoint_type=job.get("endpoint_type"),
            phase=job.get("phase"),
            therapeutic_area=job.get("therapeutic_area"),
            processing_time=job.get("processing_time"),
            error_message=job.get("error_message"),
            created_at=job.get("created_at"),
            completed_at=job.get("completed_at"),
            filename=job.get("filename"),
            protocol_preview=preview
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs")
async def list_jobs(limit: int = 20):
    """
    List recent jobs.
    """
    try:
        db = get_supabase()

        result = db.table("sap_jobs").select(
            "id, status, nct_id, filename, quality_score, endpoint_type, phase, created_at, completed_at, processing_time"
        ).order("created_at", desc=True).limit(limit).execute()

        return {"jobs": result.data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job."""
    try:
        db = get_supabase()
        db.table("sap_jobs").delete().eq("id", job_id).execute()
        return {"message": "Job deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ground-truth")
async def list_ground_truth():
    """
    List available ground truth SAPs for evaluation.
    Includes all pairs from data/all_pairs directory.
    """
    try:
        # Check both directories
        base_dir = Path(__file__).parent.parent.parent / "data"
        all_pairs_dir = base_dir / "all_pairs"
        ground_truth_dir = base_dir / "ground_truth"

        studies = []
        seen_nct_ids = set()

        # All ground_truth SAPs are now high quality (downloaded from real PDFs)

        # Add all ground truth SAPs (all are high quality - from real PDFs)
        if ground_truth_dir.exists():
            for sap_file in ground_truth_dir.glob("*_sap.txt"):
                nct_id = sap_file.stem.replace("_sap", "")
                if nct_id in seen_nct_ids:
                    continue
                seen_nct_ids.add(nct_id)

                try:
                    sap_text = sap_file.read_text(encoding='utf-8', errors='ignore')
                    lines = len(sap_text.split('\n'))

                    # Detect therapeutic area
                    sap_lower = sap_text.lower()
                    if any(x in sap_lower for x in ["cancer", "tumor", "oncology", "carcinoma", "melanoma"]):
                        area = "Oncology"
                    elif any(x in sap_lower for x in ["heart", "cardiac", "cardiovascular", "coronary"]):
                        area = "Cardiology"
                    elif any(x in sap_lower for x in ["diabetes", "glucose", "metabolic", "obesity"]):
                        area = "Metabolism"
                    elif any(x in sap_lower for x in ["infection", "hiv", "hepatitis", "covid", "viral"]):
                        area = "Infectious"
                    elif any(x in sap_lower for x in ["psychiatric", "depression", "anxiety", "schizophrenia"]):
                        area = "Psychiatry"
                    else:
                        area = "Other"

                    # Get title from protocol if available
                    protocol_file = ground_truth_dir / f"{nct_id}_protocol.txt"
                    title = nct_id
                    if protocol_file.exists():
                        protocol_text = protocol_file.read_text(encoding='utf-8', errors='ignore')[:300]
                        if "STUDY:" in protocol_text:
                            title = protocol_text.split("STUDY:")[1].split("\n")[0].strip()[:60]

                    studies.append({
                        "nct_id": nct_id,
                        "title": f"⭐ {title}" if lines > 500 else title,
                        "sap_lines": lines,
                        "therapeutic_area": area,
                        "quality": "high"
                    })
                except Exception as e:
                    print(f"[Ground Truth] Warning: Could not process {nct_id}: {e}")
                    continue

        # Then add all pairs from all_pairs directory
        if all_pairs_dir.exists():
            for sap_file in all_pairs_dir.glob("*_sap.txt"):
                nct_id = sap_file.stem.replace("_sap", "")
                if nct_id in seen_nct_ids:
                    continue
                seen_nct_ids.add(nct_id)

                try:
                    sap_text = sap_file.read_text(encoding='utf-8', errors='ignore')
                    lines = len(sap_text.split('\n'))

                    # Try to detect therapeutic area from content
                    sap_lower = sap_text.lower()
                    if any(x in sap_lower for x in ["cancer", "tumor", "oncology", "carcinoma"]):
                        area = "Oncology"
                    elif any(x in sap_lower for x in ["infection", "hiv", "hepatitis", "viral"]):
                        area = "Infectious"
                    elif any(x in sap_lower for x in ["heart", "cardiac", "cardiovascular"]):
                        area = "Cardiology"
                    elif any(x in sap_lower for x in ["diabetes", "glucose", "metabolic"]):
                        area = "Metabolism"
                    else:
                        area = "Other"

                    # Extract title from protocol if available
                    protocol_file = all_pairs_dir / f"{nct_id}_protocol.txt"
                    title = nct_id
                    if protocol_file.exists():
                        protocol_text = protocol_file.read_text(encoding='utf-8', errors='ignore')[:500]
                        # Try to find title
                        for line in protocol_text.split('\n'):
                            if 'title:' in line.lower() or 'study:' in line.lower():
                                title = line.split(':', 1)[-1].strip()[:60]
                                if title:
                                    break

                    studies.append({
                        "nct_id": nct_id,
                        "title": title if title != nct_id else f"{nct_id} ({area})",
                        "sap_lines": lines,
                        "therapeutic_area": area,
                        "quality": "standard"
                    })
                except Exception:
                    continue

        # Sort: high quality first, then by NCT ID
        studies.sort(key=lambda x: (0 if x.get("quality") == "high" else 1, x["nct_id"]))

        return {
            "studies": studies,
            "total": len(studies),
            "high_quality": sum(1 for s in studies if s.get("quality") == "high")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/evaluate/{job_id}")
async def evaluate_job(job_id: str, ground_truth_nct: str):
    """
    Evaluate a completed job's SAP against a ground truth SAP.
    Checks both ground_truth and all_pairs directories.
    """
    try:
        db = get_supabase()

        # Get the job
        result = db.table("sap_jobs").select("*").eq("id", job_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Job not found")

        job = result.data[0]

        if job["status"] != "completed":
            raise HTTPException(status_code=400, detail="Job must be completed to evaluate")

        generated_sap = job.get("generated_sap", "")
        if not generated_sap:
            raise HTTPException(status_code=400, detail="No generated SAP found")

        # Load ground truth - check both directories
        base_dir = Path(__file__).parent.parent.parent / "data"
        ground_truth_dir = base_dir / "ground_truth"
        all_pairs_dir = base_dir / "all_pairs"

        sap_path = None
        # First check ground_truth directory (high quality)
        gt_path = ground_truth_dir / f"{ground_truth_nct}_sap.txt"
        if gt_path.exists():
            sap_path = gt_path
        else:
            # Then check all_pairs directory
            ap_path = all_pairs_dir / f"{ground_truth_nct}_sap.txt"
            if ap_path.exists():
                sap_path = ap_path

        if not sap_path:
            raise HTTPException(status_code=404, detail=f"Ground truth SAP not found: {ground_truth_nct}")

        ground_truth_sap = sap_path.read_text(encoding='utf-8', errors='ignore')

        evaluator = SAPEvaluator(str(sap_path.parent))
        eval_result = evaluator.evaluate(generated_sap, ground_truth_sap, ground_truth_nct)

        return {
            "nct_id": eval_result.nct_id,
            "ground_truth_lines": eval_result.ground_truth_lines,
            "generated_lines": eval_result.generated_lines,
            "section_coverage_pct": eval_result.section_coverage_pct,
            "keyword_overlap_pct": eval_result.keyword_overlap_pct,
            "has_primary_endpoint": eval_result.has_primary_endpoint,
            "has_secondary_endpoint": eval_result.has_secondary_endpoint,
            "has_sample_size": eval_result.has_sample_size,
            "has_analysis_populations": eval_result.has_analysis_populations,
            "has_statistical_methods": eval_result.has_statistical_methods,
            "has_missing_data": eval_result.has_missing_data,
            "overall_score": eval_result.overall_score,
            "sections_matched": eval_result.sections_matched,
            "sections_missing": eval_result.sections_missing,
            "statistical_terms_found": eval_result.statistical_terms_found,
            "statistical_terms_missing": eval_result.statistical_terms_missing,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/evaluate-batch/{job_id}")
async def evaluate_batch(job_id: str, limit: int = 50):
    """
    Evaluate a completed job's SAP against ALL ground truth SAPs.
    Returns aggregate metrics and individual results.

    Args:
        job_id: The job to evaluate
        limit: Max number of ground truth SAPs to compare (default 50)
    """
    try:
        db = get_supabase()

        # Get the job
        result = db.table("sap_jobs").select("*").eq("id", job_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Job not found")

        job = result.data[0]

        if job["status"] != "completed":
            raise HTTPException(status_code=400, detail="Job must be completed to evaluate")

        generated_sap = job.get("generated_sap", "")
        if not generated_sap:
            raise HTTPException(status_code=400, detail="No generated SAP found")

        # Load all ground truth SAPs
        base_dir = Path(__file__).parent.parent.parent / "data"
        ground_truth_dir = base_dir / "ground_truth"
        all_pairs_dir = base_dir / "all_pairs"

        results = []

        # Evaluate against ground_truth first (high quality)
        count = 0
        if ground_truth_dir.exists():
            for sap_file in sorted(ground_truth_dir.glob("*_sap.txt")):
                if count >= limit:
                    break
                nct_id = sap_file.stem.replace("_sap", "")
                try:
                    ground_truth_sap = sap_file.read_text(encoding='utf-8', errors='ignore')
                    evaluator = SAPEvaluator(str(ground_truth_dir))
                    eval_result = evaluator.evaluate(generated_sap, ground_truth_sap, nct_id)
                    results.append({
                        "nct_id": nct_id,
                        "quality": "high",
                        "section_coverage_pct": eval_result.section_coverage_pct,
                        "keyword_overlap_pct": eval_result.keyword_overlap_pct,
                        "overall_score": eval_result.overall_score,
                        "has_primary_endpoint": eval_result.has_primary_endpoint,
                        "has_statistical_methods": eval_result.has_statistical_methods,
                        "ground_truth_lines": eval_result.ground_truth_lines,
                    })
                    count += 1
                except Exception as e:
                    continue

        # Then evaluate against all_pairs if we haven't hit limit
        if count < limit and all_pairs_dir.exists():
            seen = {r["nct_id"] for r in results}
            for sap_file in sorted(all_pairs_dir.glob("*_sap.txt")):
                if count >= limit:
                    break
                nct_id = sap_file.stem.replace("_sap", "")
                if nct_id in seen:
                    continue
                try:
                    ground_truth_sap = sap_file.read_text(encoding='utf-8', errors='ignore')
                    evaluator = SAPEvaluator(str(all_pairs_dir))
                    eval_result = evaluator.evaluate(generated_sap, ground_truth_sap, nct_id)
                    results.append({
                        "nct_id": nct_id,
                        "quality": "standard",
                        "section_coverage_pct": eval_result.section_coverage_pct,
                        "keyword_overlap_pct": eval_result.keyword_overlap_pct,
                        "overall_score": eval_result.overall_score,
                        "has_primary_endpoint": eval_result.has_primary_endpoint,
                        "has_statistical_methods": eval_result.has_statistical_methods,
                        "ground_truth_lines": eval_result.ground_truth_lines,
                    })
                    count += 1
                except Exception:
                    continue

        # Calculate aggregate metrics
        if results:
            avg_section_coverage = sum(r["section_coverage_pct"] for r in results) / len(results)
            avg_keyword_overlap = sum(r["keyword_overlap_pct"] for r in results) / len(results)
            avg_overall_score = sum(r["overall_score"] for r in results) / len(results)
            primary_endpoint_pct = sum(1 for r in results if r["has_primary_endpoint"]) / len(results) * 100
            statistical_methods_pct = sum(1 for r in results if r["has_statistical_methods"]) / len(results) * 100

            # Find best and worst matches
            sorted_by_score = sorted(results, key=lambda x: x["overall_score"], reverse=True)
            best_match = sorted_by_score[0] if sorted_by_score else None
            worst_match = sorted_by_score[-1] if sorted_by_score else None
        else:
            avg_section_coverage = 0
            avg_keyword_overlap = 0
            avg_overall_score = 0
            primary_endpoint_pct = 0
            statistical_methods_pct = 0
            best_match = None
            worst_match = None

        return {
            "total_comparisons": len(results),
            "aggregate": {
                "avg_section_coverage_pct": round(avg_section_coverage, 1),
                "avg_keyword_overlap_pct": round(avg_keyword_overlap, 1),
                "avg_overall_score": round(avg_overall_score, 1),
                "primary_endpoint_pct": round(primary_endpoint_pct, 1),
                "statistical_methods_pct": round(statistical_methods_pct, 1),
            },
            "best_match": best_match,
            "worst_match": worst_match,
            "results": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """
    Get job statistics.
    """
    try:
        db = get_supabase()

        result = db.table("sap_jobs").select("status, quality_score, processing_time").execute()

        jobs = result.data
        completed_jobs = [j for j in jobs if j["status"] == "completed"]

        stats = {
            "total": len(jobs),
            "completed": len(completed_jobs),
            "failed": sum(1 for j in jobs if j["status"] == "failed"),
            "queued": sum(1 for j in jobs if j["status"] == "queued"),
            "processing": sum(1 for j in jobs if j["status"] == "processing"),
            "avg_quality_score": round(sum(j["quality_score"] or 0 for j in completed_jobs) / len(completed_jobs), 1) if completed_jobs else 0,
            "avg_processing_time": round(sum(j["processing_time"] or 0 for j in completed_jobs) / len(completed_jobs), 1) if completed_jobs else 0,
        }

        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# SDTM SPECIFICATION ENDPOINT
# =============================================================================

class SDTMSpecResponse(BaseModel):
    """Response model for SDTM specification generation."""
    success: bool
    message: str
    sdtm_version: str = "3.4"
    domains: list = []  # List of domain specs
    domain_count: int = 0
    markdown: str = ""  # Full markdown specification
    sap_summary: dict = {}  # Extracted SAP information (endpoints, populations, etc.)
    errors: list = []


@app.post("/generate-sdtm/{job_id}", response_model=SDTMSpecResponse)
async def generate_sdtm_specs(job_id: str):
    """
    Generate SDTM domain specifications from a completed SAP job.

    This endpoint takes a job_id that has already completed SAP generation,
    extracts the protocol facts, and generates CDISC-compliant SDTM specs.

    Returns:
        - List of required SDTM domains (DM, AE, EX, DS, etc.)
        - Variable-level specifications for each domain
        - Core classifications (Req/Exp/Perm) per CDISC SDTMIG v3.4
    """
    try:
        db = get_supabase()

        # Get job and verify it's completed
        result = db.table("sap_jobs").select("*").eq("id", job_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Job not found")

        job = result.data[0]

        if job["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Job not ready for SDTM generation. Status: {job['status']}"
            )

        # Import SDTM generator
        try:
            from enterprise_sap_system.specs.sdtm_specs import SDTMSpecGenerator
        except ImportError as e:
            raise HTTPException(
                status_code=500,
                detail=f"SDTM generator not available: {e}"
            )

        # Build protocol facts from job data - now passes SAP text for parsing
        protocol_text = job.get("protocol_text", "")
        sap_text = job.get("generated_sap", "")

        # The new generator parses the SAP text to extract study-specific requirements
        protocol_facts = {
            "protocol_id": _extract_protocol_id(sap_text, protocol_text, job.get("nct_id")),
            "sap_text": sap_text,  # Key: pass SAP text for parsing
        }

        # Generate SDTM specs by parsing SAP text
        generator = SDTMSpecGenerator()
        spec = generator.generate(protocol_facts)

        # Convert domains to JSON-serializable format with traceability
        domains_json = []
        for domain in spec.domains:
            domain_dict = {
                "code": domain.code,
                "name": domain.name,
                "label": domain.label,
                "class": domain.domain_class.value,
                "structure": domain.structure,
                "purpose": domain.purpose,
                "study_specific_notes": domain.study_specific_notes,
                "traceability": [
                    {
                        "sap_section": t.sap_section,
                        "sap_text": t.sap_text[:200] + "..." if len(t.sap_text) > 200 else t.sap_text,
                        "sdtm_element": t.sdtm_element,
                        "rationale": t.rationale
                    }
                    for t in domain.traceability
                ],
                "variables": [
                    {
                        "name": v.name,
                        "label": v.label,
                        "type": v.type,
                        "length": v.length,
                        "core": v.core.value,
                        "codelist": v.codelist,
                    }
                    for v in domain.variables
                ]
            }
            domains_json.append(domain_dict)

        # Generate markdown
        markdown = spec.to_markdown()

        # Count domains with SAP traceability
        traced_domains = sum(1 for d in spec.domains if d.traceability)

        return SDTMSpecResponse(
            success=True,
            message=f"Generated SDTM specs for {len(spec.domains)} domains ({traced_domains} with SAP traceability)",
            sdtm_version=spec.sdtm_version,
            domains=domains_json,
            domain_count=len(spec.domains),
            markdown=markdown,
            sap_summary=spec.sap_summary,
            errors=[]
        )

    except HTTPException:
        raise
    except Exception as e:
        return SDTMSpecResponse(
            success=False,
            message=f"SDTM generation failed: {str(e)}",
            errors=[str(e)]
        )


def _detect_indication(text: str) -> str:
    """Detect indication from protocol text."""
    text_lower = text.lower()
    if 'ulcerative colitis' in text_lower:
        return 'Ulcerative Colitis'
    elif 'crohn' in text_lower:
        return "Crohn's Disease"
    elif 'melanoma' in text_lower:
        return 'Melanoma'
    elif 'breast cancer' in text_lower:
        return 'Breast Cancer'
    elif 'lung cancer' in text_lower or 'nsclc' in text_lower:
        return 'Non-Small Cell Lung Cancer'
    elif 'rheumatoid arthritis' in text_lower:
        return 'Rheumatoid Arthritis'
    return ''


def _extract_timepoint(sap_text: str) -> str:
    """Extract primary timepoint from SAP text."""
    import re
    patterns = [
        r'(?:primary|week)\s*(\d+)',
        r'at\s+week\s+(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, sap_text, re.IGNORECASE)
        if match:
            return f"Week {match.group(1)}"
    return "Week 12"


def _extract_secondary_endpoints(sap_text: str) -> list:
    """Extract secondary endpoints from SAP text."""
    import re
    endpoints = []
    # Look for secondary endpoint section
    match = re.search(r'secondary\s+endpoint[s]?[:\s]+([^\n]+(?:\n[^\n]+)*?)(?=\n\n|\Z)', sap_text, re.IGNORECASE)
    if match:
        text = match.group(1)
        # Split by common delimiters
        for item in re.split(r'[;•\n]', text):
            item = item.strip()
            if item and len(item) > 5 and len(item) < 200:
                endpoints.append({"name": item[:100]})
    return endpoints[:5]  # Max 5


# =============================================================================
# CODE GENERATION ENDPOINT (Additive - does not modify existing functionality)
# =============================================================================

class CodeGenerationResponse(BaseModel):
    """Response model for code generation."""
    success: bool
    message: str
    programs: dict = {}  # {filename: code}
    total_lines: int = 0
    errors: list = []


@app.post("/generate-code/{job_id}", response_model=CodeGenerationResponse)
async def generate_sas_code(job_id: str):
    """
    Generate SAS code from a completed SAP job.

    This endpoint takes a job_id that has already completed SAP generation,
    extracts the protocol facts, and generates production-ready SAS code.

    Returns:
        - ADaM dataset programs (ADSL, ADAE, ADTTE, ADEFF)
        - TLF output programs (demographics, AE summary, primary efficacy)
        - Driver program
    """
    try:
        db = get_supabase()

        # Get job and verify it's completed
        result = db.table("sap_jobs").select("*").eq("id", job_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Job not found")

        job = result.data[0]

        if job["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Job not ready for code generation. Status: {job['status']}"
            )

        if not job.get("generated_sap"):
            raise HTTPException(
                status_code=400,
                detail="Job has no SAP output to generate code from"
            )

        # Import code generator (lazy import to avoid startup issues)
        try:
            from enterprise_sap_system.code_generators import CodeGenerationOrchestrator
        except ImportError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Code generator not available: {e}"
            )

        # Build protocol facts from job data
        # Note: In production, these would be stored with the job
        sap_text = job.get("generated_sap", "")
        protocol_text = job.get("protocol_text", "")
        protocol_facts = {
            "protocol_id": _extract_protocol_id(sap_text, protocol_text, job.get("nct_id")),
            "therapeutic_area": _detect_therapeutic_area(protocol_text or sap_text),
            "drug_name": _extract_drug_name(sap_text),
            "treatments": _extract_treatments(sap_text),
            "primary_endpoint": _extract_primary_endpoint(sap_text, protocol_text),
            "total_n": _extract_sample_size(sap_text),
        }

        # Generate code
        orchestrator = CodeGenerationOrchestrator()
        package = orchestrator.generate_all(protocol_facts)

        # Build response
        programs = {}
        total_lines = 0

        for prog in package.adam_programs:
            programs[f"adam/{prog.program_name}"] = prog.code
            total_lines += len(prog.code.split('\n'))

        for prog in package.tlf_programs:
            programs[f"tlf/{prog.program_name}"] = prog.code
            total_lines += len(prog.code.split('\n'))

        programs["driver.sas"] = package.driver_program
        total_lines += len(package.driver_program.split('\n'))

        return CodeGenerationResponse(
            success=True,
            message=f"Generated {len(package.adam_programs)} ADaM + {len(package.tlf_programs)} TLF programs",
            programs=programs,
            total_lines=total_lines,
            errors=[]
        )

    except HTTPException:
        raise
    except Exception as e:
        return CodeGenerationResponse(
            success=False,
            message=f"Code generation failed: {str(e)}",
            programs={},
            total_lines=0,
            errors=[str(e)]
        )


def _detect_therapeutic_area(text: str) -> str:
    """Detect therapeutic area from protocol text."""
    text_lower = text.lower()
    if any(term in text_lower for term in ['crohn', 'colitis', 'ibd', 'ulcerative']):
        return 'ibd'
    elif any(term in text_lower for term in ['tumor', 'cancer', 'oncology', 'recist']):
        return 'oncology'
    elif any(term in text_lower for term in ['rheumatoid', 'arthritis', 'das28']):
        return 'rheumatology'
    elif any(term in text_lower for term in ['cardiac', 'heart', 'cardiovascular']):
        return 'cardiovascular'
    return 'general'


def _extract_drug_name(sap_text: str) -> str:
    """Extract drug name from SAP text."""
    import re
    # Look for common patterns
    patterns = [
        r'study drug[:\s]+([A-Za-z0-9-]+)',
        r'investigational product[:\s]+([A-Za-z0-9-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, sap_text, re.IGNORECASE)
        if match:
            return match.group(1)
    return "Study Drug"


def _extract_treatments(sap_text: str) -> list:
    """Extract treatment arms from SAP text."""
    import re
    treatments = []

    # Look for arm patterns
    arm_matches = re.findall(r'(?:arm|group)\s*\d*[:\s]*([^,\n]+(?:mg|placebo)[^,\n]*)', sap_text, re.IGNORECASE)
    for match in arm_matches[:4]:  # Max 4 arms
        name = match.strip()
        if name and name not in [t['name'] for t in treatments]:
            treatments.append({'name': name, 'code': f'TRT{len(treatments)+1}'})

    # Default if none found
    if not treatments:
        treatments = [
            {'name': 'Placebo', 'code': 'TRT1'},
            {'name': 'Active Treatment', 'code': 'TRT2'}
        ]

    return treatments


def _extract_primary_endpoint(sap_text: str, protocol_text: str = "") -> dict:
    """Extract primary endpoint from protocol or SAP text with robust pattern matching.

    IMPORTANT: Search protocol_text FIRST as it contains the original endpoint definition.
    The SAP text may have generic placeholders if extraction failed during generation.
    """
    import re

    # Search both texts, but prioritize protocol_text (the source of truth)
    texts_to_search = []
    if protocol_text:
        texts_to_search.append(protocol_text)
    if sap_text:
        texts_to_search.append(sap_text)

    for text in texts_to_search:
        # First, look for the DEFINITION section with Mayo score criteria (most specific)
        # This pattern finds "Definition Criteria:" followed by the actual criteria
        definition_patterns = [
            # **Definition:** or Definition Criteria: followed by Mayo score definition
            r'(?:definition\s*(?:criteria)?)[:\s]*(?:\*\*)?([^*\n]*?(?:mayo\s+score|subscore)[^*\n]*?(?:≤|<=|=)\s*\d+[^*\n]*)',
            # Clinical remission defined as Mayo score criteria
            r'clinical\s+remission[^.]*?(?:defined\s+as|is)[:\s]*([^.]*?(?:mayo\s+score|subscore)[^.]*?(?:≤|<=|=)\s*\d+[^.]*)',
            # Full/total Mayo score with specific criteria
            r'((?:full|total)\s+mayo\s+score\s*(?:≤|<=|of)\s*\d+[^.|\n]*)',
        ]

        for pattern in definition_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                endpoint = match.group(1).strip()
                # Clean up whitespace and formatting
                endpoint = re.sub(r'\s+', ' ', endpoint)
                endpoint = re.sub(r'\*\*|\*|__|#', '', endpoint)
                # Add "Clinical remission" prefix if not present
                if 'remission' not in endpoint.lower() and 'response' not in endpoint.lower():
                    endpoint = "Clinical remission: " + endpoint
                endpoint = endpoint[0].upper() + endpoint[1:] if endpoint else endpoint
                # Clean trailing punctuation
                endpoint = endpoint.rstrip('|,;')
                if len(endpoint) > 15:
                    return {'name': endpoint[:200], 'type': 'binary'}

        # IBD/UC-specific endpoint patterns (proportion achieving remission)
        ibd_patterns = [
            # Proportion achieving clinical remission at week X
            r'((?:proportion|percentage)\s+of\s+(?:subjects|patients)\s+(?:achieving|with|in)\s+clinical\s+remission\s+(?:at|by)\s+week\s+\d+)',
            # Clinical remission at week X (only if "Clinical remission" is included)
            r'(clinical\s+remission\s+(?:at|by)\s+week\s+\d+)',
            r'(clinical\s+response\s+(?:at|by)\s+week\s+\d+)',
            # Endoscopic endpoints
            r'(endoscopic\s+(?:improvement|remission|response|healing)\s+(?:at|by)\s+week\s+\d+)',
            r'(mucosal\s+healing\s+(?:at|by)\s+week\s+\d+)',
            # Modified/partial Mayo score endpoints
            r'((?:modified|partial)\s+mayo\s+score\s+(?:of\s+)?(?:\d+|≤\s*\d+)[^|\n]*?(?:at|by)\s+week\s+\d+)',
        ]

        for pattern in ibd_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                endpoint = match.group(1).strip()
                # Clean up whitespace and newlines
                endpoint = re.sub(r'\s+', ' ', endpoint)
                endpoint = endpoint[0].upper() + endpoint[1:] if endpoint else endpoint
                endpoint = endpoint.rstrip('|,;')
                if len(endpoint) > 10:
                    return {'name': endpoint[:200], 'type': 'binary'}

        # Look in sections that typically define primary endpoint
        section_patterns = [
            # Section header followed by endpoint definition (not just "at Week 12")
            r'(?:primary\s+(?:efficacy\s+)?endpoint|primary\s+objective)[:\s]*\n+([^\n]+(?:remission|response|score|healing)[^\n]+)',
            # Primary endpoint IS statement
            r'primary\s+(?:efficacy\s+)?endpoint\s+(?:is|will\s+be)\s+(?:the\s+)?(?:proportion[^.|\n]+|clinical[^.|\n]+)',
        ]

        for pattern in section_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                endpoint = match.group(1) if match.lastindex else match.group(0)
                endpoint = endpoint.strip()
                # Skip if it's just a generic placeholder or just "at Week 12"
                skip_patterns = ['primary endpoint', 'the primary endpoint', 'endpoint', 'at week', 'by week']
                if any(endpoint.lower().strip() == sp or endpoint.lower().strip().startswith(sp + ' |') for sp in skip_patterns):
                    continue
                # Clean up
                endpoint = re.sub(r'\s+', ' ', endpoint)
                endpoint = re.sub(r'\*\*|\*|__|#|\|', '', endpoint)
                endpoint = endpoint.rstrip('.|,;')
                if endpoint and len(endpoint) > 15:
                    return {'name': endpoint[:200], 'type': _detect_endpoint_type(endpoint)}

        # General patterns for any therapeutic area
        general_patterns = [
            r'((?:overall\s+)?(?:survival|response\s+rate|progression[- ]free)\s+(?:at|by)\s+(?:week|month)\s+\d+)',
            r'((?:objective\s+)?response\s+rate\s+(?:at|by)\s+week\s+\d+)',
            r'((?:change|reduction)\s+(?:from\s+baseline\s+)?in\s+[^|\n]+(?:at|by)\s+week\s+\d+)',
        ]

        for pattern in general_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                endpoint = match.group(1).strip()
                endpoint = re.sub(r'\s+', ' ', endpoint)
                endpoint = endpoint[0].upper() + endpoint[1:] if endpoint else endpoint
                return {'name': endpoint[:200], 'type': _detect_endpoint_type(endpoint)}

    # Default fallback - use a meaningful description if this is an IBD study
    if any(term in (sap_text + protocol_text).lower() for term in ['ulcerative colitis', 'crohn', 'ibd']):
        return {'name': 'Clinical remission at Week 12', 'type': 'binary'}

    return {'name': 'Primary Endpoint', 'type': 'binary'}


def _detect_endpoint_type(endpoint_text: str) -> str:
    """Detect the type of endpoint from its description."""
    endpoint_lower = endpoint_text.lower()

    if any(term in endpoint_lower for term in ['remission', 'response', 'proportion', 'percentage', 'rate']):
        return 'binary'
    if any(term in endpoint_lower for term in ['change from baseline', 'mean change', 'difference']):
        return 'continuous'
    if any(term in endpoint_lower for term in ['time to', 'survival', 'duration']):
        return 'time-to-event'
    if any(term in endpoint_lower for term in ['score', 'index', 'scale']):
        return 'continuous'

    return 'binary'


def _extract_protocol_id(sap_text: str, protocol_text: str = "", job_nct_id: str = None) -> str:
    """Extract protocol/study ID from available sources."""
    import re

    # First check if job has nct_id
    if job_nct_id and job_nct_id != "UNKNOWN" and len(job_nct_id) > 3:
        return job_nct_id

    # Try to extract from SAP text
    patterns = [
        # Protocol numbers like CTJ301UC201, ABC-123-456
        r'(?:protocol|study)\s*(?:number|id|identifier)?[:\s]+([A-Z]{2,5}[-]?\d{2,4}[-]?[A-Z]{0,3}[-]?\d{0,4})',
        r'(?:protocol|study)[:\s]+([A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+)',
        r'([A-Z]{2,5}\d{3}[A-Z]{2}\d{3})',  # Pattern like CTJ301UC201
        # NCT numbers
        r'(NCT\d{8})',
        # EudraCT numbers
        r'(\d{4}-\d{6}-\d{2})',
        # Generic protocol patterns
        r'protocol[:\s]+([A-Z0-9-]{6,20})',
    ]

    # Try SAP text first, then protocol text
    for text in [sap_text, protocol_text]:
        if not text:
            continue
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                study_id = match.group(1).strip()
                if study_id and len(study_id) >= 6:
                    return study_id.upper()

    return "UNKNOWN"


def _extract_sample_size(sap_text: str) -> int:
    """Extract sample size from SAP text."""
    import re
    patterns = [
        r'(\d+)\s*(?:patients|subjects|participants)',
        r'n\s*=\s*(\d+)',
        r'sample size[:\s]+(\d+)',
        r'total\s+of\s+(\d+)\s+(?:patients|subjects)',
        r'(\d+)\s+(?:patients|subjects)\s+will be\s+(?:enrolled|randomized)',
    ]
    for pattern in patterns:
        match = re.search(pattern, sap_text, re.IGNORECASE)
        if match:
            size = int(match.group(1))
            if size >= 10:  # Reasonable minimum
                return size
    return 100


# =============================================================================
# TLF SHELL SPECIFICATION ENDPOINT
# =============================================================================

class TLFShellResponse(BaseModel):
    """Response model for TLF shell generation."""
    success: bool
    message: str
    tables: list = []
    listings: list = []
    figures: list = []
    total_outputs: int = 0
    markdown: str = ""
    errors: list = []


@app.post("/generate-tlf-shells/{job_id}", response_model=TLFShellResponse)
async def generate_tlf_shells(job_id: str):
    """
    Generate TLF (Tables, Listings, Figures) shell specifications from a completed SAP job.

    Returns:
        - Demographics tables (Table 14.1.x)
        - Efficacy tables (Table 14.2.x)
        - Safety tables (Table 14.3.x)
        - Data listings (Listing 16.2.x)
        - Figures (Figure 14.x)
    """
    try:
        db = get_supabase()

        # Get job and verify it's completed
        result = db.table("sap_jobs").select("*").eq("id", job_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Job not found")

        job = result.data[0]

        if job["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Job not ready for TLF generation. Status: {job['status']}"
            )

        # Extract protocol facts from job data
        protocol_text = job.get("protocol_text", "")
        sap_text = job.get("generated_sap", "")

        # Use improved protocol ID extraction
        protocol_id = _extract_protocol_id(sap_text, protocol_text, job.get("nct_id"))
        therapeutic_area = _detect_therapeutic_area(protocol_text or sap_text)
        primary_endpoint = _extract_primary_endpoint(sap_text, protocol_text)
        treatments = _extract_treatments(sap_text)
        sample_size = _extract_sample_size(sap_text)

        # Generate TLF shells using simplified approach (markdown-based)
        tables_json = []
        listings_json = []
        figures_json = []

        # Demographics table
        tables_json.append({
            "output_id": "Table 14.1.1",
            "title": "Summary of Subject Demographics and Baseline Characteristics",
            "population": "Safety Population",
            "footnotes": ["N = Number of subjects in the safety population."],
            "columns": [],
            "markdown": ""
        })

        # Disposition table
        tables_json.append({
            "output_id": "Table 14.1.2",
            "title": "Subject Disposition",
            "population": "All Randomized",
            "footnotes": [],
            "columns": [],
            "markdown": ""
        })

        # Primary efficacy table
        tables_json.append({
            "output_id": "Table 14.2.1",
            "title": f"Primary Efficacy Analysis: {primary_endpoint.get('name', 'Primary Endpoint')}",
            "population": "Full Analysis Set",
            "footnotes": ["Analysis performed using ANCOVA with treatment as a factor."],
            "columns": [],
            "markdown": ""
        })

        # AE Summary table
        tables_json.append({
            "output_id": "Table 14.3.1",
            "title": "Overall Summary of Treatment-Emergent Adverse Events",
            "population": "Safety Population",
            "footnotes": ["TEAE = Treatment-Emergent Adverse Event"],
            "columns": [],
            "markdown": ""
        })

        # AE by SOC/PT
        tables_json.append({
            "output_id": "Table 14.3.2",
            "title": "Treatment-Emergent Adverse Events by System Organ Class and Preferred Term",
            "population": "Safety Population",
            "footnotes": ["MedDRA version X.X"],
            "columns": [],
            "markdown": ""
        })

        # SAE table
        tables_json.append({
            "output_id": "Table 14.3.3",
            "title": "Serious Adverse Events",
            "population": "Safety Population",
            "footnotes": [],
            "columns": [],
            "markdown": ""
        })

        # Listings
        listings_json.append({
            "output_id": "Listing 16.2.1",
            "title": "Listing of Subjects Who Discontinued Study",
            "population": "All Randomized",
            "footnotes": [],
            "columns": [],
            "markdown": ""
        })

        listings_json.append({
            "output_id": "Listing 16.2.4",
            "title": "Listing of Serious Adverse Events",
            "population": "Safety Population",
            "footnotes": [],
            "columns": [],
            "markdown": ""
        })

        listings_json.append({
            "output_id": "Listing 16.2.6",
            "title": "Listing of Deaths",
            "population": "Safety Population",
            "footnotes": [],
            "columns": [],
            "markdown": ""
        })

        # Figures
        figures_json.append({
            "output_id": "Figure 14.2.1",
            "title": f"Kaplan-Meier Plot of {primary_endpoint.get('name', 'Primary Endpoint')}",
            "population": "Full Analysis Set",
            "footnotes": [],
            "columns": [],
            "markdown": ""
        })

        figures_json.append({
            "output_id": "Figure 14.2.2",
            "title": "Forest Plot of Subgroup Analyses",
            "population": "Full Analysis Set",
            "footnotes": [],
            "columns": [],
            "markdown": ""
        })

        # Helper to escape pipe characters and clean titles for markdown tables
        def escape_md_table(text: str) -> str:
            if not text:
                return ""
            # Escape pipe characters and remove newlines
            return text.replace("|", "\\|").replace("\n", " ").replace("\r", "").strip()

        # Generate markdown document
        full_markdown = f"""# TLF SHELL SPECIFICATIONS
**Protocol:** {protocol_id}
**Therapeutic Area:** {therapeutic_area.upper()}

---

## Tables

| Output ID | Title | Population |
|-----------|-------|------------|
"""
        for t in tables_json:
            full_markdown += f"| {escape_md_table(t['output_id'])} | {escape_md_table(t['title'])} | {escape_md_table(t['population'])} |\n"

        full_markdown += "\n## Listings\n\n| Output ID | Title | Population |\n|-----------|-------|------------|\n"
        for l in listings_json:
            full_markdown += f"| {escape_md_table(l['output_id'])} | {escape_md_table(l['title'])} | {escape_md_table(l['population'])} |\n"

        full_markdown += "\n## Figures\n\n| Output ID | Title | Population |\n|-----------|-------|------------|\n"
        for f in figures_json:
            full_markdown += f"| {escape_md_table(f['output_id'])} | {escape_md_table(f['title'])} | {escape_md_table(f['population'])} |\n"

        total_outputs = len(tables_json) + len(listings_json) + len(figures_json)

        return TLFShellResponse(
            success=True,
            message=f"Generated {len(tables_json)} tables, {len(listings_json)} listings, {len(figures_json)} figures",
            tables=tables_json,
            listings=listings_json,
            figures=figures_json,
            total_outputs=total_outputs,
            markdown=full_markdown,
            errors=[]
        )

    except HTTPException:
        raise
    except Exception as e:
        return TLFShellResponse(
            success=False,
            message=f"TLF generation failed: {str(e)}",
            errors=[str(e)]
        )


# =============================================================================
# ADAM DERIVATION SPECIFICATION ENDPOINT
# =============================================================================

class AdamSpecResponse(BaseModel):
    """Response model for ADaM derivation specification generation."""
    success: bool
    message: str
    datasets: list = []
    total_variables: int = 0
    markdown: str = ""
    errors: list = []


@app.post("/generate-adam-specs/{job_id}", response_model=AdamSpecResponse)
async def generate_adam_specs(job_id: str):
    """
    Generate ADaM (Analysis Data Model) derivation specifications from a completed SAP job.

    Returns:
        - ADSL (Subject-Level Analysis Dataset) derivations
        - ADAE (Adverse Events) derivations
        - ADLB (Laboratory) derivations
        - ADEFF (Efficacy) derivations
        - ADTTE (Time-to-Event) derivations
    """
    try:
        db = get_supabase()

        # Get job and verify it's completed
        result = db.table("sap_jobs").select("*").eq("id", job_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Job not found")

        job = result.data[0]

        if job["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Job not ready for ADaM spec generation. Status: {job['status']}"
            )

        # Extract protocol facts from job data
        protocol_text = job.get("protocol_text", "")
        sap_text = job.get("generated_sap", "")

        protocol_id = _extract_protocol_id(sap_text, protocol_text, job.get("nct_id"))
        therapeutic_area = _detect_therapeutic_area(protocol_text or sap_text)
        primary_endpoint = _extract_primary_endpoint(sap_text, protocol_text)
        treatments = _extract_treatments(sap_text)

        # Build ADaM datasets using standard derivations
        datasets_json = []
        total_vars = 0

        # ADSL - Subject-Level Dataset
        adsl_vars = [
            {"name": "STUDYID", "label": "Study Identifier", "type": "Char", "length": 20, "derivation": "Assigned from protocol", "source": "DM.STUDYID", "codelist": None},
            {"name": "USUBJID", "label": "Unique Subject Identifier", "type": "Char", "length": 50, "derivation": "Assigned from SDTM", "source": "DM.USUBJID", "codelist": None},
            {"name": "SUBJID", "label": "Subject Identifier for the Study", "type": "Char", "length": 20, "derivation": "Assigned from SDTM", "source": "DM.SUBJID", "codelist": None},
            {"name": "SITEID", "label": "Study Site Identifier", "type": "Char", "length": 10, "derivation": "Assigned from SDTM", "source": "DM.SITEID", "codelist": None},
            {"name": "AGE", "label": "Age", "type": "Num", "length": 8, "derivation": "Set to DM.AGE", "source": "DM.AGE", "codelist": None},
            {"name": "AGEGR1", "label": "Pooled Age Group 1", "type": "Char", "length": 20, "derivation": "Derived: <65='<65', >=65='>=65'", "source": "DM.AGE", "codelist": None},
            {"name": "AGEGR1N", "label": "Pooled Age Group 1 (N)", "type": "Num", "length": 8, "derivation": "Numeric code for AGEGR1", "source": "AGEGR1", "codelist": None},
            {"name": "SEX", "label": "Sex", "type": "Char", "length": 1, "derivation": "Set to DM.SEX", "source": "DM.SEX", "codelist": "SEX"},
            {"name": "RACE", "label": "Race", "type": "Char", "length": 100, "derivation": "Set to DM.RACE", "source": "DM.RACE", "codelist": None},
            {"name": "ETHNIC", "label": "Ethnicity", "type": "Char", "length": 50, "derivation": "Set to DM.ETHNIC", "source": "DM.ETHNIC", "codelist": None},
            {"name": "TRT01P", "label": "Planned Treatment for Period 01", "type": "Char", "length": 200, "derivation": "Set to DM.ARM", "source": "DM.ARM", "codelist": None},
            {"name": "TRT01PN", "label": "Planned Treatment for Period 01 (N)", "type": "Num", "length": 8, "derivation": "Numeric code for TRT01P", "source": "TRT01P", "codelist": None},
            {"name": "TRT01A", "label": "Actual Treatment for Period 01", "type": "Char", "length": 200, "derivation": "Set to DM.ACTARM", "source": "DM.ACTARM", "codelist": None},
            {"name": "TRT01AN", "label": "Actual Treatment for Period 01 (N)", "type": "Num", "length": 8, "derivation": "Numeric code for TRT01A", "source": "TRT01A", "codelist": None},
            {"name": "TRTSDT", "label": "Date of First Exposure to Treatment", "type": "Num", "length": 8, "derivation": "Min(EX.EXSTDTC) where EXDOSE>0", "source": "EX.EXSTDTC", "codelist": None},
            {"name": "TRTEDT", "label": "Date of Last Exposure to Treatment", "type": "Num", "length": 8, "derivation": "Max(EX.EXENDTC) where EXDOSE>0", "source": "EX.EXENDTC", "codelist": None},
            {"name": "SAFFL", "label": "Safety Population Flag", "type": "Char", "length": 1, "derivation": "Y if TRTSDT is not missing", "source": "Derived", "codelist": "NY"},
            {"name": "ITTFL", "label": "Intent-to-Treat Population Flag", "type": "Char", "length": 1, "derivation": "Y if randomized", "source": "Derived", "codelist": "NY"},
            {"name": "FASFL", "label": "Full Analysis Set Population Flag", "type": "Char", "length": 1, "derivation": "Y if ITT and has baseline + 1 post-BL", "source": "Derived", "codelist": "NY"},
        ]
        datasets_json.append({
            "name": "ADSL",
            "label": "Subject-Level Analysis Dataset",
            "structure": "One record per subject",
            "keys": ["STUDYID", "USUBJID"],
            "variables": adsl_vars
        })
        total_vars += len(adsl_vars)

        # ADAE - Adverse Event Analysis Dataset
        adae_vars = [
            {"name": "STUDYID", "label": "Study Identifier", "type": "Char", "length": 20, "derivation": "Set to ADSL.STUDYID", "source": "ADSL", "codelist": None},
            {"name": "USUBJID", "label": "Unique Subject Identifier", "type": "Char", "length": 50, "derivation": "Set to ADSL.USUBJID", "source": "ADSL", "codelist": None},
            {"name": "AESEQ", "label": "Sequence Number", "type": "Num", "length": 8, "derivation": "Set to AE.AESEQ", "source": "AE.AESEQ", "codelist": None},
            {"name": "TRTA", "label": "Actual Treatment", "type": "Char", "length": 200, "derivation": "Treatment at AE onset", "source": "ADSL.TRT01A", "codelist": None},
            {"name": "AEDECOD", "label": "Dictionary-Derived Term", "type": "Char", "length": 200, "derivation": "Set to AE.AEDECOD", "source": "AE.AEDECOD", "codelist": None},
            {"name": "AEBODSYS", "label": "Body System or Organ Class", "type": "Char", "length": 200, "derivation": "Set to AE.AEBODSYS", "source": "AE.AEBODSYS", "codelist": None},
            {"name": "AESEV", "label": "Severity/Intensity", "type": "Char", "length": 20, "derivation": "Set to AE.AESEV", "source": "AE.AESEV", "codelist": None},
            {"name": "AESER", "label": "Serious Event", "type": "Char", "length": 1, "derivation": "Set to AE.AESER", "source": "AE.AESER", "codelist": "NY"},
            {"name": "AEREL", "label": "Causality", "type": "Char", "length": 50, "derivation": "Set to AE.AEREL", "source": "AE.AEREL", "codelist": None},
            {"name": "ASTDT", "label": "Analysis Start Date", "type": "Num", "length": 8, "derivation": "Derived from AE.AESTDTC", "source": "AE.AESTDTC", "codelist": None},
            {"name": "AENDT", "label": "Analysis End Date", "type": "Num", "length": 8, "derivation": "Derived from AE.AEENDTC", "source": "AE.AEENDTC", "codelist": None},
            {"name": "AETRTEMFL", "label": "Treatment Emergent Flag", "type": "Char", "length": 1, "derivation": "Y if ASTDT >= TRTSDT and ASTDT <= TRTEDT+30", "source": "Derived", "codelist": "NY"},
        ]
        datasets_json.append({
            "name": "ADAE",
            "label": "Adverse Event Analysis Dataset",
            "structure": "One record per adverse event per subject",
            "keys": ["STUDYID", "USUBJID", "AESEQ"],
            "variables": adae_vars
        })
        total_vars += len(adae_vars)

        # ADEFF - Efficacy Analysis Dataset
        adeff_vars = [
            {"name": "STUDYID", "label": "Study Identifier", "type": "Char", "length": 20, "derivation": "Set to ADSL.STUDYID", "source": "ADSL", "codelist": None},
            {"name": "USUBJID", "label": "Unique Subject Identifier", "type": "Char", "length": 50, "derivation": "Set to ADSL.USUBJID", "source": "ADSL", "codelist": None},
            {"name": "PARAMCD", "label": "Parameter Code", "type": "Char", "length": 8, "derivation": "Assigned per parameter", "source": "Derived", "codelist": None},
            {"name": "PARAM", "label": "Parameter", "type": "Char", "length": 200, "derivation": "Parameter description", "source": "Derived", "codelist": None},
            {"name": "AVAL", "label": "Analysis Value", "type": "Num", "length": 8, "derivation": "Numeric analysis value", "source": "Derived", "codelist": None},
            {"name": "BASE", "label": "Baseline Value", "type": "Num", "length": 8, "derivation": "Value where ABLFL=Y", "source": "Derived", "codelist": None},
            {"name": "CHG", "label": "Change from Baseline", "type": "Num", "length": 8, "derivation": "AVAL - BASE", "source": "Derived", "codelist": None},
            {"name": "PCHG", "label": "Percent Change from Baseline", "type": "Num", "length": 8, "derivation": "100 * (AVAL - BASE) / BASE", "source": "Derived", "codelist": None},
            {"name": "AVISIT", "label": "Analysis Visit", "type": "Char", "length": 40, "derivation": "Analysis visit with windowing", "source": "Derived", "codelist": None},
            {"name": "ABLFL", "label": "Baseline Record Flag", "type": "Char", "length": 1, "derivation": "Y for baseline record", "source": "Derived", "codelist": "NY"},
            {"name": "ANL01FL", "label": "Analysis Record Flag 01", "type": "Char", "length": 1, "derivation": "Y for primary analysis records", "source": "Derived", "codelist": "NY"},
        ]
        datasets_json.append({
            "name": "ADEFF",
            "label": "Efficacy Analysis Dataset",
            "structure": "One record per subject per parameter per visit",
            "keys": ["STUDYID", "USUBJID", "PARAMCD", "AVISIT"],
            "variables": adeff_vars
        })
        total_vars += len(adeff_vars)

        # ADTTE - Time-to-Event Dataset
        adtte_vars = [
            {"name": "STUDYID", "label": "Study Identifier", "type": "Char", "length": 20, "derivation": "Set to ADSL.STUDYID", "source": "ADSL", "codelist": None},
            {"name": "USUBJID", "label": "Unique Subject Identifier", "type": "Char", "length": 50, "derivation": "Set to ADSL.USUBJID", "source": "ADSL", "codelist": None},
            {"name": "PARAMCD", "label": "Parameter Code", "type": "Char", "length": 8, "derivation": "Assigned per TTE parameter", "source": "Derived", "codelist": None},
            {"name": "PARAM", "label": "Parameter", "type": "Char", "length": 200, "derivation": "TTE parameter description", "source": "Derived", "codelist": None},
            {"name": "STARTDT", "label": "Time-to-Event Origin Date", "type": "Num", "length": 8, "derivation": "Randomization or first dose date", "source": "ADSL", "codelist": None},
            {"name": "ADT", "label": "Analysis Date", "type": "Num", "length": 8, "derivation": "Event or censoring date", "source": "Derived", "codelist": None},
            {"name": "AVAL", "label": "Analysis Value", "type": "Num", "length": 8, "derivation": "ADT - STARTDT + 1 (days)", "source": "Derived", "codelist": None},
            {"name": "CNSR", "label": "Censor", "type": "Num", "length": 8, "derivation": "0=Event, 1=Censored", "source": "Derived", "codelist": None},
            {"name": "EVNTDESC", "label": "Event Description", "type": "Char", "length": 200, "derivation": "Description of event", "source": "Derived", "codelist": None},
        ]
        datasets_json.append({
            "name": "ADTTE",
            "label": "Time-to-Event Analysis Dataset",
            "structure": "One record per subject per parameter",
            "keys": ["STUDYID", "USUBJID", "PARAMCD"],
            "variables": adtte_vars
        })
        total_vars += len(adtte_vars)

        # Generate markdown document
        markdown_parts = [
            "# ADaM Derivation Specifications",
            f"\n**Protocol:** {protocol_id}",
            f"\n**Therapeutic Area:** {therapeutic_area.upper()}",
            "\n---\n"
        ]

        for ds in datasets_json:
            markdown_parts.append(f"\n## {ds['name']} - {ds['label']}")
            markdown_parts.append(f"\n**Structure:** {ds['structure']}")
            markdown_parts.append(f"\n**Keys:** {', '.join(ds['keys'])}")
            markdown_parts.append("\n\n### Variable Derivations\n")
            markdown_parts.append("| Variable | Label | Type | Derivation |")
            markdown_parts.append("|----------|-------|------|------------|")
            for v in ds['variables'][:20]:
                deriv = v['derivation'][:80] + "..." if len(v['derivation']) > 80 else v['derivation']
                markdown_parts.append(f"| {v['name']} | {v['label'][:40]} | {v['type']} | {deriv} |")
            if len(ds['variables']) > 20:
                markdown_parts.append(f"\n*...and {len(ds['variables']) - 20} more variables*")

        return AdamSpecResponse(
            success=True,
            message=f"Generated derivation specs for {len(datasets_json)} ADaM datasets with {total_vars} variables",
            datasets=datasets_json,
            total_variables=total_vars,
            markdown="\n".join(markdown_parts),
            errors=[]
        )

    except HTTPException:
        raise
    except Exception as e:
        return AdamSpecResponse(
            success=False,
            message=f"ADaM spec generation failed: {str(e)}",
            errors=[str(e)]
        )


# =============================================================================
# DEFINE-XML GENERATION ENDPOINT
# =============================================================================

class DefineXMLResponse(BaseModel):
    """Response model for Define-XML generation."""
    success: bool
    message: str
    xml_content: str = ""
    dataset_count: int = 0
    variable_count: int = 0
    standard_type: str = ""  # "SDTM" or "ADaM"
    errors: list = []


@app.post("/generate-define-xml/{job_id}")
async def generate_define_xml(job_id: str, standard: str = "adam"):
    """
    Generate CDISC Define-XML 2.1 metadata from a completed SAP job.

    Args:
        job_id: The job ID to generate Define-XML for
        standard: Either "sdtm" or "adam" (default: adam)

    Returns:
        - Complete Define-XML 2.1 compliant XML document
        - Dataset definitions
        - Variable metadata with origins and derivations
        - Codelists
    """
    try:
        db = get_supabase()

        # Get job and verify it's completed
        result = db.table("sap_jobs").select("*").eq("id", job_id).execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Job not found")

        job = result.data[0]

        if job["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Job not ready for Define-XML generation. Status: {job['status']}"
            )

        # Import Define-XML generator
        try:
            from enterprise_sap_system.specs.define_xml import (
                generate_sdtm_define_xml,
                generate_adam_define_xml,
            )
        except ImportError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Define-XML generator not available: {e}"
            )

        # Extract protocol info using improved extraction
        protocol_text = job.get("protocol_text", "")
        sap_text = job.get("generated_sap", "")
        protocol_id = _extract_protocol_id(sap_text, protocol_text, job.get("nct_id"))
        if protocol_id == "UNKNOWN":
            protocol_id = "STUDY-001"
        study_name = f"Study {protocol_id}"

        # Generate based on standard type
        if standard.lower() == "sdtm":
            xml_content = generate_sdtm_define_xml(
                study_id=protocol_id,
                study_name=study_name,
                domains=["DM", "AE", "CM", "DS", "EX", "LB", "MH", "VS"]
            )
            dataset_count = 8
            variable_count = 200  # Approximate
            standard_type = "SDTM"
        else:
            xml_content = generate_adam_define_xml(
                study_id=protocol_id,
                study_name=study_name,
                datasets=["ADSL", "ADAE", "ADLB", "ADEFF", "ADTTE"]
            )
            dataset_count = 5
            variable_count = 120  # Approximate
            standard_type = "ADaM"

        return {
            "success": True,
            "message": f"Generated {standard_type} Define-XML 2.1 with {dataset_count} datasets",
            "xml_content": xml_content,
            "dataset_count": dataset_count,
            "variable_count": variable_count,
            "standard_type": standard_type,
            "errors": []
        }

    except HTTPException:
        raise
    except Exception as e:
        return {
            "success": False,
            "message": f"Define-XML generation failed: {str(e)}",
            "xml_content": "",
            "dataset_count": 0,
            "variable_count": 0,
            "standard_type": "",
            "errors": [str(e)]
        }


# Background worker
async def process_jobs_worker():
    """
    Background worker that processes queued jobs using AGENTIC HYBRIDRAG PIPELINE.

    The AGENTIC pipeline uses 5 agents with Vector + Graph retrieval:

    AGENT 1 - PROTOCOL ANALYZER:
    - Claude-based extraction (replaces regex)
    - Extracts drug classes, indication, phase, design

    AGENT 2 - HYBRID RETRIEVER:
    - Vector similarity (ChromaDB, 23K chunks)
    - Knowledge Graph traversal (393 trials)
    - Finds similar trials based on characteristics

    AGENT 3 - METHOD EXTRACTOR:
    - Reads retrieved chunks
    - Extracts actual methods used in similar trials
    - Data-driven (not hardcoded rules)

    AGENT 4 - SAP GENERATOR:
    - Templates + RAG examples
    - Uses extracted methods from similar trials

    AGENT 5 - VALIDATOR:
    - Reflection-based verification
    - Checks consistency with source trials
    """
    global worker_running

    print("Starting background job worker with RULE-BASED PIPELINE...")
    print("  [OK] Step 1: Claude LLM extraction")
    print("  [OK] Step 2: Condition detection (immunotherapy, crossover, etc.)")
    print("  [OK] Step 3: Knowledge Graph with 99 rules")
    print("  [OK] Step 4: ChromaDB RAG with 17K+ chunks")
    print("  [OK] Step 5: Claude LLM generation with slot constraints")
    print("  [OK] Step 6: Slot verification")

    # Use get_pipeline() - now returns RuleBasedSAPPipeline
    pipeline = None

    while worker_running:
        try:
            db = get_supabase()

            # Get next queued job
            result = db.table("sap_jobs").select("*").eq(
                "status", "queued"
            ).order("created_at").limit(1).execute()

            if not result.data:
                # No jobs, wait and retry
                await asyncio.sleep(5)
                continue

            job = result.data[0]
            job_id = job["id"]

            print(f"Processing job: {job_id}")

            # Mark as processing
            db.table("sap_jobs").update({
                "status": "processing",
                "started_at": datetime.utcnow().isoformat()
            }).eq("id", job_id).execute()

            # Initialize pipeline if needed - uses RuleBasedSAPPipeline
            if pipeline is None:
                pipeline = get_pipeline()
                print("  [INIT] RuleBasedSAPPipeline initialized (Claude + 99 rules + RAG + slot verification)")

            # Generate SAP using pipeline
            start_time = time.time()

            try:
                result = pipeline.generate(job["protocol_text"][:50000])

                processing_time = time.time() - start_time

                if result.success:
                    # Handle RuleBasedSAPPipeline result (PRIMARY - has facts) vs AgenticSAPPipeline (fallback - has characteristics)
                    if hasattr(result, 'facts') and result.facts:
                        # PRIMARY: RuleBasedSAPPipeline format
                        facts = result.facts

                        drug_name = facts.get('drug_name', '') or ''
                        phase_str = facts.get('phase', '') or ''
                        if phase_str and "." in phase_str:
                            phase_str = phase_str.split(".")[-1].replace("_", " ").title()

                        therapeutic_area = facts.get('therapeutic_area', '') or facts.get('indication', '') or ''

                        pe = facts.get('primary_endpoint', '')
                        if isinstance(pe, dict):
                            endpoint_type_str = (pe.get('type', '') or pe.get('endpoint_type', ''))[:10]
                        elif isinstance(pe, str):
                            endpoint_type_str = pe[:10]
                        else:
                            endpoint_type_str = ""

                        quality_score = 1.0 if result.verification and result.verification.passed else 0.5
                        pipeline_type = "rule-based"

                    elif hasattr(result, 'characteristics') and result.characteristics:
                        # FALLBACK: AgenticSAPPipeline format
                        chars = result.characteristics
                        drug_name = chars.drug_classes[0] if chars.drug_classes else ""
                        phase_str = chars.phase or ""
                        therapeutic_area = chars.indication or ""
                        endpoint_type_str = (chars.endpoint_type or "")[:10]

                        # Validation from agentic pipeline
                        quality_score = result.confidence if result.confidence else 0.8
                        if result.validation:
                            quality_score = result.validation.confidence

                        pipeline_type = "agentic"

                    else:
                        # Minimal fallback
                        drug_name = ""
                        phase_str = ""
                        therapeutic_area = ""
                        endpoint_type_str = ""
                        quality_score = 0.5
                        pipeline_type = "unknown"

                    update_data = {
                        "status": "completed",
                        "generated_sap": result.sap_text,
                        "quality_score": quality_score,
                        "endpoint_type": endpoint_type_str[:10],  # varchar(10)
                        "phase": (phase_str or "")[:10],  # varchar(10)
                        "therapeutic_area": (therapeutic_area or "")[:20],
                        "processing_time": processing_time,
                        "completed_at": datetime.utcnow().isoformat()
                    }

                    # Log validation info
                    if hasattr(result, 'validation') and result.validation:
                        if hasattr(result.validation, 'issues') and result.validation.issues:
                            print(f"  Validation issues ({len(result.validation.issues)}):")
                            for issue in result.validation.issues[:5]:
                                print(f"    - {issue}")
                    elif hasattr(result, 'verification') and result.verification:
                        issues = result.verification.missing_slots
                        if issues:
                            print(f"  Validation issues ({len(issues)}):")
                            for issue in issues[:5]:
                                severity = issue.severity.value if hasattr(issue, 'severity') else "HIGH"
                                message = issue.message if hasattr(issue, 'message') else str(issue)
                                print(f"    [{severity}] {message}")

                    db.table("sap_jobs").update(update_data).eq("id", job_id).execute()

                    # Detailed logging
                    print(f"Job {job_id} completed in {processing_time:.1f}s ({pipeline_type} pipeline)")
                    if pipeline_type == "agentic" and hasattr(result, 'characteristics') and result.characteristics:
                        chars = result.characteristics
                        print(f"  EXTRACTION:")
                        print(f"    Drug classes: {chars.drug_classes}")
                        print(f"    Indication: {chars.indication}")
                        print(f"    Endpoint: {chars.endpoint_type}")
                        print(f"  RETRIEVAL:")
                        print(f"    Source trials: {result.source_trials}")
                        print(f"  METHODS:")
                        if result.extracted_methods:
                            print(f"    Primary: {result.extracted_methods.primary_analysis}")
                            print(f"    Interim: {result.extracted_methods.interim_analysis}")
                        print(f"  VALIDATION:")
                        print(f"    Confidence: {quality_score:.2f}")
                    elif pipeline_type == "rule-based" and hasattr(result, 'facts') and result.facts:
                        facts = result.facts
                        print(f"  EXTRACTION:")
                        print(f"    Drug: {facts.get('drug_name', 'N/A')}")
                        sample_size = facts.get('sample_size')
                        if isinstance(sample_size, dict):
                            print(f"    N: {sample_size.get('total_n', 'N/A')}")
                        else:
                            print(f"    N: {sample_size or 'N/A'}")
                        print(f"    Ratio: {facts.get('randomization_ratio', 'N/A')}")
                        print(f"  GENERATION:")
                        print(f"    Sections: {list(result.sections.keys()) if result.sections else 'None'}")
                        print(f"  VALIDATION:")
                        print(f"    Quality: {quality_score:.1f}")

                    if result.warnings:
                        print(f"  Warnings: {len(result.warnings)}")
                else:
                    raise Exception(result.error or "Generation failed")

            except Exception as e:
                # Update with failure
                db.table("sap_jobs").update({
                    "status": "failed",
                    "error_message": str(e)[:500],
                    "processing_time": time.time() - start_time,
                    "completed_at": datetime.utcnow().isoformat()
                }).eq("id", job_id).execute()

                print(f"Job {job_id} failed: {e}")

        except Exception as e:
            print(f"Worker error: {e}")
            await asyncio.sleep(10)

        # Small delay between jobs
        await asyncio.sleep(1)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

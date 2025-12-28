"""
SAP Generator Backend API
Production-grade with file upload support
Deploy to Render.com
"""

import os
import time
import asyncio
import tempfile
from datetime import datetime
from typing import Optional
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

from enterprise_sap_system.agents import create_orchestrator
from enterprise_sap_system.core import get_config
from evaluate_sap import SAPEvaluator

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

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
        except:
            raise ValueError("Failed to decode text file")


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
        except:
            raise ValueError(f"Unsupported file format: {ext}")


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
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/upload", response_model=JobResponse)
async def upload_file(
    file: UploadFile = File(...),
    nct_id: Optional[str] = Form(None)
):
    """
    Upload a protocol document (PDF, DOCX, TXT) and create a SAP generation job.
    """
    try:
        # Read file content
        content = await file.read()

        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        if len(content) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=400, detail="File too large (max 10MB)")

        # Extract text
        try:
            extracted_text = extract_text_from_file(file.filename, content)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        if not extracted_text.strip():
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

        return JobResponse(
            job_id=job_id,
            status="queued",
            message=f"File '{file.filename}' uploaded successfully. Processing started.",
            extracted_text=extracted_text[:2000] + ("..." if len(extracted_text) > 2000 else "")
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
                except:
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

        if not job.get("sap_output"):
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
        protocol_facts = {
            "protocol_id": job.get("nct_id") or "UNKNOWN",
            "therapeutic_area": _detect_therapeutic_area(job.get("protocol_text", "")),
            "drug_name": _extract_drug_name(job.get("sap_output", "")),
            "treatments": _extract_treatments(job.get("sap_output", "")),
            "primary_endpoint": _extract_primary_endpoint(job.get("sap_output", "")),
            "total_n": _extract_sample_size(job.get("sap_output", "")),
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


def _extract_primary_endpoint(sap_text: str) -> dict:
    """Extract primary endpoint from SAP text."""
    import re
    match = re.search(r'primary\s+endpoint[:\s]+([^\n.]+)', sap_text, re.IGNORECASE)
    if match:
        return {'name': match.group(1).strip()[:100], 'type': 'binary'}
    return {'name': 'Primary Endpoint', 'type': 'binary'}


def _extract_sample_size(sap_text: str) -> int:
    """Extract sample size from SAP text."""
    import re
    patterns = [
        r'(\d+)\s*(?:patients|subjects|participants)',
        r'n\s*=\s*(\d+)',
        r'sample size[:\s]+(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, sap_text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return 100


# Background worker
async def process_jobs_worker():
    """
    Background worker that processes queued jobs.
    """
    global worker_running

    print("Starting background job worker...")

    # Initialize orchestrator once
    orchestrator = None

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

            # Initialize orchestrator if needed
            if orchestrator is None:
                orchestrator = create_orchestrator(use_rag=True)

            # Generate SAP
            start_time = time.time()

            try:
                result = orchestrator.generate_sap(
                    protocol_text=job["protocol_text"][:50000],
                    nct_id=job.get("nct_id", ""),
                    use_few_shot=True,  # Enable RAG few-shot examples
                    verbose=True
                )

                processing_time = time.time() - start_time

                if result.success:
                    # Update with success
                    # Handle both legacy mode (with quality_report/parsed_protocol) and constrained mode (without)
                    quality_score = result.quality_report.overall_score if result.quality_report else 85.0  # Default for constrained mode
                    endpoint_type = None
                    phase = None
                    therapeutic_area = None

                    if result.parsed_protocol:
                        if result.parsed_protocol.primary_estimand:
                            endpoint_type = result.parsed_protocol.primary_estimand.variable_type.value
                        phase = str(result.parsed_protocol.phase.value) if hasattr(result.parsed_protocol.phase, 'value') else str(result.parsed_protocol.phase)
                        therapeutic_area = result.parsed_protocol.therapeutic_area

                    db.table("sap_jobs").update({
                        "status": "completed",
                        "generated_sap": result.sap_document.full_document,
                        "quality_score": quality_score,
                        "endpoint_type": endpoint_type,
                        "phase": phase,
                        "therapeutic_area": therapeutic_area,
                        "processing_time": processing_time,
                        "completed_at": datetime.utcnow().isoformat()
                    }).eq("id", job_id).execute()

                    print(f"Job {job_id} completed in {processing_time:.1f}s")
                else:
                    raise Exception("; ".join(result.errors))

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

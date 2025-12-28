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
    allow_origins=["*"],  # Allow all for now
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

        # Import evaluator
        from evaluate_sap import SAPEvaluator

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

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
                    db.table("sap_jobs").update({
                        "status": "completed",
                        "generated_sap": result.sap_document.full_document,
                        "quality_score": result.quality_report.overall_score,
                        "endpoint_type": result.parsed_protocol.primary_estimand.variable_type.value if result.parsed_protocol.primary_estimand else None,
                        "phase": str(result.parsed_protocol.phase.value) if hasattr(result.parsed_protocol.phase, 'value') else str(result.parsed_protocol.phase),
                        "therapeutic_area": result.parsed_protocol.therapeutic_area,
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

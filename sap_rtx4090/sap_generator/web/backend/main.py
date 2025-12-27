"""
SAP Generator Backend API
Deploy to Render.com
"""

import os
import time
import asyncio
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

# Supabase client
from supabase import create_client, Client

# Import SAP generator (add parent to path)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from enterprise_sap_system.agents import create_orchestrator
from enterprise_sap_system.core import get_config

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Use service role key for backend
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
    version="1.0.0",
    lifespan=lifespan
)

# CORS for Vercel frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.vercel.app",
        os.getenv("FRONTEND_URL", ""),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class GenerateRequest(BaseModel):
    protocol_text: str
    nct_id: Optional[str] = None


class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str


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


# API Endpoints
@app.get("/")
async def root():
    return {"status": "ok", "message": "SAP Generator API"}


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/generate", response_model=JobResponse)
async def create_job(request: GenerateRequest):
    """
    Create a new SAP generation job.
    Returns job_id immediately, processing happens in background.
    """
    try:
        db = get_supabase()

        # Insert job into database
        result = db.table("sap_jobs").insert({
            "protocol_text": request.protocol_text,
            "nct_id": request.nct_id,
            "status": "queued"
        }).execute()

        job_id = result.data[0]["id"]

        return JobResponse(
            job_id=job_id,
            status="queued",
            message="Job created. Poll /status/{job_id} for results."
        )

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
            completed_at=job.get("completed_at")
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs")
async def list_jobs(limit: int = 10):
    """
    List recent jobs.
    """
    try:
        db = get_supabase()

        result = db.table("sap_jobs").select(
            "id, status, nct_id, quality_score, endpoint_type, created_at, completed_at"
        ).order("created_at", desc=True).limit(limit).execute()

        return {"jobs": result.data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """
    Get job statistics.
    """
    try:
        db = get_supabase()

        # Get counts by status
        result = db.table("sap_jobs").select("status").execute()

        stats = {
            "total": len(result.data),
            "completed": sum(1 for j in result.data if j["status"] == "completed"),
            "failed": sum(1 for j in result.data if j["status"] == "failed"),
            "queued": sum(1 for j in result.data if j["status"] == "queued"),
            "processing": sum(1 for j in result.data if j["status"] == "processing"),
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
                    use_few_shot=False,
                    verbose=False
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

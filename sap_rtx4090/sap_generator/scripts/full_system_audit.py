#!/usr/bin/env python3
"""
Full System Audit for SAP Generator
====================================
Comprehensive audit of all system components.
"""

import sys
import os
import json
from pathlib import Path
from datetime import datetime

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 70)
print("SAP GENERATOR FULL SYSTEM AUDIT")
print(f"Timestamp: {datetime.now().isoformat()}")
print("=" * 70)

# Track overall status
audit_results = {
    "passed": 0,
    "failed": 0,
    "warnings": 0,
    "details": {}
}

def check(name, condition, warning_only=False):
    """Record a check result."""
    if condition:
        print(f"  ✅ {name}")
        audit_results["passed"] += 1
        audit_results["details"][name] = "PASS"
    elif warning_only:
        print(f"  ⚠️  {name}")
        audit_results["warnings"] += 1
        audit_results["details"][name] = "WARNING"
    else:
        print(f"  ❌ {name}")
        audit_results["failed"] += 1
        audit_results["details"][name] = "FAIL"
    return condition


# =============================================================================
# 1. DEPENDENCIES
# =============================================================================
print("\n" + "=" * 70)
print("1. DEPENDENCIES")
print("=" * 70)

deps = {}

# Core dependencies
try:
    import requests
    deps["requests"] = requests.__version__
    check("requests", True)
except ImportError:
    check("requests", False)

try:
    import pdfplumber
    deps["pdfplumber"] = pdfplumber.__version__
    check("pdfplumber", True)
except ImportError:
    check("pdfplumber", False, warning_only=True)

try:
    import chromadb
    deps["chromadb"] = chromadb.__version__
    check("chromadb", True)
except ImportError:
    check("chromadb (RAG vector store)", False)

try:
    from sentence_transformers import SentenceTransformer
    deps["sentence_transformers"] = True
    check("sentence-transformers", True)
except ImportError:
    check("sentence-transformers (embeddings)", False)

try:
    import anthropic
    deps["anthropic"] = anthropic.__version__
    check("anthropic SDK", True)
except ImportError:
    check("anthropic SDK", False, warning_only=True)

try:
    import openai
    deps["openai"] = openai.__version__
    check("openai SDK", True)
except ImportError:
    check("openai SDK", False, warning_only=True)

try:
    import fastapi
    deps["fastapi"] = fastapi.__version__
    check("fastapi", True)
except ImportError:
    check("fastapi (web API)", False)

try:
    import pydantic
    deps["pydantic"] = pydantic.__version__
    check("pydantic", True)
except ImportError:
    check("pydantic", False)

# =============================================================================
# 2. CORE MODULES
# =============================================================================
print("\n" + "=" * 70)
print("2. CORE MODULES")
print("=" * 70)

try:
    from enterprise_sap_system.core.hybrid_pipeline import HybridSAPPipeline, create_hybrid_pipeline
    check("HybridSAPPipeline", True)
except ImportError as e:
    check(f"HybridSAPPipeline: {e}", False)

try:
    from enterprise_sap_system.core.claude_extractor import ClaudeProtocolExtractor
    check("ClaudeProtocolExtractor", True)
except ImportError as e:
    check(f"ClaudeProtocolExtractor: {e}", False)

try:
    from enterprise_sap_system.core.hybrid_reasoning import HybridReasoningEngine
    check("HybridReasoningEngine", True)
except ImportError as e:
    check(f"HybridReasoningEngine: {e}", False)

try:
    from enterprise_sap_system.core.schemas import StructuredFactExtractor
    check("StructuredFactExtractor", True)
except ImportError as e:
    check(f"StructuredFactExtractor: {e}", False)

try:
    from enterprise_sap_system.core.llm_section_generator import LLMSectionGenerator
    check("LLMSectionGenerator", True)
except ImportError as e:
    check(f"LLMSectionGenerator: {e}", False)

try:
    from enterprise_sap_system.core.hard_validator import HardValidator
    check("HardValidator", True)
except ImportError as e:
    check(f"HardValidator: {e}", False)

try:
    from enterprise_sap_system.core.contamination_guard import ContaminationGuard
    check("ContaminationGuard", True)
except ImportError as e:
    check(f"ContaminationGuard: {e}", False)

# =============================================================================
# 3. RAG SYSTEM
# =============================================================================
print("\n" + "=" * 70)
print("3. RAG VECTOR STORE")
print("=" * 70)

try:
    from enterprise_sap_system.rag.vector_store import SAPVectorStore, create_vector_store

    store = create_vector_store()
    stats = store.get_collection_stats()

    total_docs = sum(stats.values())
    check(f"Vector store initialized ({total_docs} total documents)", True)

    # Check critical collections
    critical_collections = {
        "time_to_event": 100,
        "subgroup_analysis": 50,
        "sensitivity_analysis": 50,
        "secondary_endpoints": 50,
        "primary_analysis": 50,
    }

    print("\n  Collection counts:")
    for name, count in sorted(stats.items(), key=lambda x: -x[1]):
        min_required = critical_collections.get(name, 0)
        status = "✅" if count >= min_required else "⚠️" if count > 0 else "❌"
        print(f"    {status} {name}: {count}")

    # Verify critical gaps are filled
    check("time_to_event >= 100 docs", stats.get("time_to_event", 0) >= 100)
    check("subgroup_analysis >= 50 docs", stats.get("subgroup_analysis", 0) >= 50)
    check("sensitivity_analysis >= 50 docs", stats.get("sensitivity_analysis", 0) >= 50)

except Exception as e:
    check(f"RAG Vector Store: {e}", False)

# =============================================================================
# 4. TRAINING DATA
# =============================================================================
print("\n" + "=" * 70)
print("4. TRAINING DATA")
print("=" * 70)

rag_data_dir = Path(__file__).parent.parent / "rag_training_data"
specialized_dir = rag_data_dir / "specialized_saps"

check(f"RAG training data dir exists", rag_data_dir.exists())
check(f"Specialized SAPs dir exists", specialized_dir.exists())

if specialized_dir.exists():
    # Count oncology PDFs
    oncology_dir = specialized_dir / "oncology_phase3"
    if oncology_dir.exists():
        pdfs = list(oncology_dir.glob("*.pdf"))
        check(f"Oncology SAP PDFs downloaded ({len(pdfs)})", len(pdfs) >= 30)

    # Count indexed chunks
    chunk_dirs = [d for d in specialized_dir.iterdir() if d.is_dir() and d.name.startswith("sap_")]
    total_chunks = 0
    for chunk_dir in chunk_dirs:
        total_chunks += len(list(chunk_dir.glob("*.txt")))
    check(f"Total indexed chunks ({total_chunks})", total_chunks >= 10000)

    # Check RAG index
    rag_index = specialized_dir / "rag_index.json"
    check("RAG index file exists", rag_index.exists())

# =============================================================================
# 5. API KEYS / ENVIRONMENT
# =============================================================================
print("\n" + "=" * 70)
print("5. ENVIRONMENT / API KEYS")
print("=" * 70)

check("ANTHROPIC_API_KEY set", bool(os.environ.get("ANTHROPIC_API_KEY")), warning_only=True)
check("OPENAI_API_KEY set", bool(os.environ.get("OPENAI_API_KEY")), warning_only=True)
check("GROQ_API_KEY set", bool(os.environ.get("GROQ_API_KEY")), warning_only=True)

# =============================================================================
# 6. WEB API
# =============================================================================
print("\n" + "=" * 70)
print("6. WEB API")
print("=" * 70)

try:
    from web.backend.main import app
    check("FastAPI app imports", True)
except ImportError as e:
    check(f"FastAPI app: {e}", False, warning_only=True)

# Check if server is running
try:
    import requests
    response = requests.get("http://localhost:8000/health", timeout=2)
    check(f"API server running (status: {response.status_code})", response.status_code == 200)
except Exception:
    check("API server running", False, warning_only=True)

# =============================================================================
# 7. PIPELINE INTEGRATION TEST
# =============================================================================
print("\n" + "=" * 70)
print("7. PIPELINE INTEGRATION TEST")
print("=" * 70)

try:
    from enterprise_sap_system.core.hybrid_pipeline import create_hybrid_pipeline

    pipeline = create_hybrid_pipeline()
    check("Pipeline instantiation", pipeline is not None)

    # Check pipeline has required components
    check("Pipeline has extractor", hasattr(pipeline, 'extractor') or hasattr(pipeline, 'regex_extractor'))
    check("Pipeline has reasoning engine", hasattr(pipeline, 'reasoning_engine'))
    check("Pipeline has section generator", hasattr(pipeline, 'section_generator'))

except Exception as e:
    check(f"Pipeline integration: {e}", False)

# =============================================================================
# 8. FILE STRUCTURE
# =============================================================================
print("\n" + "=" * 70)
print("8. FILE STRUCTURE")
print("=" * 70)

base_dir = Path(__file__).parent.parent

critical_files = [
    "enterprise_sap_system/core/hybrid_pipeline.py",
    "enterprise_sap_system/core/claude_extractor.py",
    "enterprise_sap_system/core/hybrid_reasoning.py",
    "enterprise_sap_system/core/llm_section_generator.py",
    "enterprise_sap_system/rag/vector_store.py",
    "web/backend/main.py",
]

for file_path in critical_files:
    full_path = base_dir / file_path
    check(f"{file_path}", full_path.exists())

# =============================================================================
# SUMMARY
# =============================================================================
print("\n" + "=" * 70)
print("AUDIT SUMMARY")
print("=" * 70)

print(f"""
  ✅ Passed:   {audit_results['passed']}
  ⚠️  Warnings: {audit_results['warnings']}
  ❌ Failed:   {audit_results['failed']}
""")

if audit_results['failed'] == 0:
    print("🎉 SYSTEM AUDIT PASSED - All critical checks OK")
    exit_code = 0
elif audit_results['failed'] <= 3:
    print("⚠️  SYSTEM AUDIT: Minor issues detected")
    exit_code = 1
else:
    print("❌ SYSTEM AUDIT FAILED - Critical issues found")
    exit_code = 2

print("=" * 70)

# Save audit results
audit_file = base_dir / "audit_results.json"
audit_results["timestamp"] = datetime.now().isoformat()
audit_results["dependencies"] = deps
audit_file.write_text(json.dumps(audit_results, indent=2))
print(f"\nAudit results saved to: {audit_file}")

sys.exit(exit_code)

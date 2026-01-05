#!/bin/bash
# Build Specialized RAG Training Data Pipeline
# =============================================
#
# This script downloads, parses, and indexes specialized SAPs for:
# - Immunotherapy trials (Fleming-Harrington, NPH, delayed effect)
# - Interim analysis (Lan-DeMets, O'Brien-Fleming)
# - PRO/QoL endpoints (LCSS, symptom deterioration)
# - Bridging/consistency studies
#
# Usage:
#   ./build_specialized_rag.sh
#
# Requirements:
#   pip install requests PyMuPDF chromadb sentence-transformers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RAG_DIR="$PROJECT_DIR/rag_training_data"
SPECIALIZED_DIR="$RAG_DIR/specialized_saps"

echo "========================================"
echo "Specialized RAG Training Data Pipeline"
echo "========================================"
echo ""
echo "Project: $PROJECT_DIR"
echo "RAG Dir: $RAG_DIR"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found"
    exit 1
fi

# Check dependencies
echo "Checking dependencies..."
python3 -c "import requests" 2>/dev/null || { echo "Installing requests..."; pip install requests; }
python3 -c "import fitz" 2>/dev/null || { echo "Installing PyMuPDF..."; pip install PyMuPDF; }
echo "✓ Dependencies OK"
echo ""

# Step 1: Download SAPs
echo "========================================"
echo "Step 1: Downloading Specialized SAPs"
echo "========================================"
python3 "$SCRIPT_DIR/download_specialized_saps.py" "$SPECIALIZED_DIR"

# Step 2: Parse PDFs
echo ""
echo "========================================"
echo "Step 2: Parsing PDFs into Sections"
echo "========================================"
python3 "$SCRIPT_DIR/parse_specialized_saps.py" "$SPECIALIZED_DIR" "$RAG_DIR"

# Step 3: Index into Vector Store (optional - requires more deps)
echo ""
echo "========================================"
echo "Step 3: Indexing into Vector Store"
echo "========================================"
if python3 -c "import chromadb; import sentence_transformers" 2>/dev/null; then
    python3 "$SCRIPT_DIR/index_specialized_saps.py" "$RAG_DIR"
else
    echo "⊘ Skipping indexing (chromadb/sentence-transformers not installed)"
    echo "  To enable: pip install chromadb sentence-transformers"
fi

echo ""
echo "========================================"
echo "PIPELINE COMPLETE"
echo "========================================"
echo ""
echo "New training data locations:"
echo "  $RAG_DIR/endpoints/"
echo "  $RAG_DIR/methods/"
echo "  $RAG_DIR/interim_analysis/"
echo "  $RAG_DIR/pro_endpoints/"
echo ""
echo "Specialized features now available:"
echo "  ✓ Fleming-Harrington weighted log-rank"
echo "  ✓ Lan-DeMets / O'Brien-Fleming interim analysis"
echo "  ✓ Hierarchical testing / gatekeeping"
echo "  ✓ Non-proportional hazards modeling"
echo "  ✓ PRO/QoL endpoints (LCSS, symptom burden)"
echo "  ✓ TTF endpoints for China regulatory"
echo ""

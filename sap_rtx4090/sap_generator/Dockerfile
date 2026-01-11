# Dockerfile for SAP Generator API with R support
# Uses Python + R for boundary calculations with gsDesign/rpact

FROM python:3.11-slim

# Install system dependencies and R
# Note: gfortran and libblas needed for gsDesign/rpact compilation
# libv8-dev needed for V8 R package dependency
RUN apt-get update && apt-get install -y --no-install-recommends \
    r-base \
    r-base-dev \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    build-essential \
    gfortran \
    libblas-dev \
    liblapack-dev \
    libv8-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install R packages for boundary calculations
# Note: clinfun needed for Phase 2, gsDesign/rpact for Phase 3
# dependencies=NA installs only required deps, not suggested ones
RUN R -e "install.packages(c('gsDesign', 'rpact', 'clinfun'), repos='https://cloud.r-project.org', dependencies=NA)" && \
    R -e "library(gsDesign); print('gsDesign OK')" && \
    R -e "library(rpact); print('rpact OK')" && \
    R -e "library(clinfun); print('clinfun OK')"

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY web/backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install rpy2 now that R is available
RUN pip install --no-cache-dir rpy2>=3.5.0

# =============================================================================
# CACHE BUSTING - Forces rebuild when VERSION changes
# =============================================================================
# Method 1: Copy VERSION file early (changes hash)
COPY enterprise_sap_system/VERSION ./VERSION_CHECK

# Method 2: ARG that can be overridden at build time
ARG CACHE_BUST=unknown
RUN echo "CACHE_BUST=${CACHE_BUST}" > /app/build_info.txt

# Method 3: Read and display VERSION during build (creates layer dependency)
RUN cat ./VERSION_CHECK && echo "Build timestamp: $(date -u +%Y%m%d_%H%M%S)" >> /app/build_info.txt

# =============================================================================
# COPY APPLICATION CODE
# =============================================================================
# Copy all necessary code
COPY enterprise_sap_system ./enterprise_sap_system
COPY chroma_db ./chroma_db
# Note: knowledge_graph is inside enterprise_sap_system, already copied above
COPY web/backend ./web/backend

# Verify VERSION in logs during build
RUN echo "=== BUILD VERSION CHECK ===" && cat ./enterprise_sap_system/VERSION && echo "==========================="

# Set Python path to find enterprise_sap_system
ENV PYTHONPATH=/app

# Expose port (Render uses PORT env var)
EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-10000}/health || exit 1

# Start command - Render sets PORT env var
CMD uvicorn web.backend.main:app --host 0.0.0.0 --port ${PORT:-10000}

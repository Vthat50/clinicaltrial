# Dockerfile for SAP Generator API with R support
# Uses Python + R for boundary calculations with gsDesign/rpact

FROM python:3.11-slim

# Install system dependencies and R
RUN apt-get update && apt-get install -y --no-install-recommends \
    r-base \
    r-base-dev \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install R packages for boundary calculations
RUN R -e "install.packages(c('gsDesign', 'rpact'), repos='https://cloud.r-project.org', quiet=TRUE)"

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY web/backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install rpy2 now that R is available
RUN pip install --no-cache-dir rpy2>=3.5.0

# Copy VERSION file first to bust cache when code changes
COPY enterprise_sap_system/VERSION ./VERSION_CHECK

# Copy all necessary code
COPY enterprise_sap_system ./enterprise_sap_system
COPY chroma_db ./chroma_db
COPY knowledge_graph ./knowledge_graph
COPY web/backend ./web/backend

# Set Python path to find enterprise_sap_system
ENV PYTHONPATH=/app

# Expose port (Render uses PORT env var)
EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-10000}/health || exit 1

# Start command - Render sets PORT env var
CMD uvicorn web.backend.main:app --host 0.0.0.0 --port ${PORT:-10000}

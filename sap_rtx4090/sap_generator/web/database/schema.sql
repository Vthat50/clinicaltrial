-- SAP Generator Database Schema for Supabase
-- Run this in Supabase SQL Editor

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Jobs table: tracks SAP generation requests
CREATE TABLE sap_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    -- Status: 'queued', 'processing', 'completed', 'failed'

    -- Input
    protocol_text TEXT NOT NULL,
    nct_id VARCHAR(20),
    filename VARCHAR(255),

    -- Output
    generated_sap TEXT,
    quality_score FLOAT,
    endpoint_type VARCHAR(20),
    phase VARCHAR(10),
    therapeutic_area VARCHAR(50),

    -- Metadata
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,

    -- Processing time in seconds
    processing_time FLOAT
);

-- Index for polling by status
CREATE INDEX idx_sap_jobs_status ON sap_jobs(status);
CREATE INDEX idx_sap_jobs_created_at ON sap_jobs(created_at DESC);

-- Row Level Security (RLS) - Optional, for public access
ALTER TABLE sap_jobs ENABLE ROW LEVEL SECURITY;

-- Policy: Allow anyone to insert jobs
CREATE POLICY "Allow public insert" ON sap_jobs
    FOR INSERT WITH CHECK (true);

-- Policy: Allow anyone to read their own jobs (by id)
CREATE POLICY "Allow public read" ON sap_jobs
    FOR SELECT USING (true);

-- Policy: Allow backend to update jobs (use service role key)
CREATE POLICY "Allow service update" ON sap_jobs
    FOR UPDATE USING (true);

-- View for job statistics
CREATE VIEW job_stats AS
SELECT
    COUNT(*) FILTER (WHERE status = 'completed') as completed_count,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
    COUNT(*) FILTER (WHERE status = 'queued') as queued_count,
    COUNT(*) FILTER (WHERE status = 'processing') as processing_count,
    AVG(processing_time) FILTER (WHERE status = 'completed') as avg_processing_time,
    AVG(quality_score) FILTER (WHERE status = 'completed') as avg_quality_score
FROM sap_jobs;

-- Function to get next queued job (for worker)
CREATE OR REPLACE FUNCTION get_next_job()
RETURNS TABLE(job_id UUID, protocol TEXT, nct VARCHAR(20))
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    UPDATE sap_jobs
    SET status = 'processing', started_at = NOW()
    WHERE id = (
        SELECT id FROM sap_jobs
        WHERE status = 'queued'
        ORDER BY created_at ASC
        LIMIT 1
        FOR UPDATE SKIP LOCKED
    )
    RETURNING id, protocol_text, nct_id;
END;
$$;

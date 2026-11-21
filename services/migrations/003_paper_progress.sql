ALTER TABLE paperlens_m1.paper_jobs
    ADD COLUMN stage text,
    ADD COLUMN stage_started_at timestamptz,
    ADD COLUMN activity text;

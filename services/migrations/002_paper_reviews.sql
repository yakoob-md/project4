CREATE TABLE paperlens_m1.paper_jobs (
    owner_id text NOT NULL,
    id uuid NOT NULL,
    question text NOT NULL,
    cutoff date NOT NULL,
    status text NOT NULL CHECK (status IN ('queued', 'ingesting', 'reviewing', 'synthesizing', 'completed', 'failed')),
    paper_text text,
    pdf bytea,
    bundle_id uuid,
    report_version integer,
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, id),
    FOREIGN KEY (owner_id, bundle_id) REFERENCES paperlens_m1.bundles,
    FOREIGN KEY (owner_id, bundle_id, report_version) REFERENCES paperlens_m1.reports (owner_id, bundle_id, version)
);

CREATE INDEX paper_jobs_queued ON paperlens_m1.paper_jobs (created_at, id) WHERE status = 'queued';

CREATE TABLE paperlens_m1.specialist_reviews (
    owner_id text NOT NULL,
    bundle_id uuid NOT NULL,
    role text NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY (owner_id, bundle_id, role),
    FOREIGN KEY (owner_id, bundle_id) REFERENCES paperlens_m1.bundles
);

CREATE TRIGGER frozen_specialist_review BEFORE UPDATE OR DELETE ON paperlens_m1.specialist_reviews
FOR EACH ROW EXECUTE FUNCTION paperlens_m1.reject_mutation();

CREATE TRIGGER frozen_report BEFORE UPDATE OR DELETE ON paperlens_m1.reports
FOR EACH ROW EXECUTE FUNCTION paperlens_m1.reject_mutation();

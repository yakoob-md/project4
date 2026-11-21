ALTER TABLE paperlens_m1.paper_jobs DROP CONSTRAINT paper_jobs_status_check;
ALTER TABLE paperlens_m1.paper_jobs
    ADD CHECK (status IN ('queued', 'ingesting', 'reviewing', 'synthesizing', 'completed', 'failed', 'cancelled')),
    ADD COLUMN dispatch_key text,
    ADD COLUMN input_digest text,
    ADD COLUMN lease_token uuid,
    ADD COLUMN lease_until timestamptz,
    ADD COLUMN attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
    ADD COLUMN deadline timestamptz NOT NULL DEFAULT (now() + interval '15 minutes'),
    ADD UNIQUE (owner_id, dispatch_key);

CREATE TABLE paperlens_m1.paper_checkpoints (
    owner_id text NOT NULL,
    run_id uuid NOT NULL,
    step text NOT NULL CHECK (step IN ('challenges', 'reply_novelty', 'reply_methodology', 'reply_dataset', 'closure', 'synthesis')),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (owner_id, run_id, step),
    FOREIGN KEY (owner_id, run_id) REFERENCES paperlens_m1.paper_jobs
);

CREATE TRIGGER frozen_paper_checkpoint BEFORE UPDATE OR DELETE ON paperlens_m1.paper_checkpoints
FOR EACH ROW EXECUTE FUNCTION paperlens_m1.reject_mutation();

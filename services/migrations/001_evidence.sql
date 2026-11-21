CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS paperlens_m1;

CREATE TABLE paperlens_m1.runs (
    owner_id text NOT NULL,
    id uuid NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY (owner_id, id)
);

CREATE TABLE paperlens_m1.input_revisions (
    owner_id text NOT NULL,
    run_id uuid NOT NULL,
    id uuid NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY (owner_id, run_id, id),
    FOREIGN KEY (owner_id, run_id) REFERENCES paperlens_m1.runs
);

CREATE TABLE paperlens_m1.bundles (
    owner_id text NOT NULL,
    run_id uuid NOT NULL,
    revision_id uuid NOT NULL,
    id uuid NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY (owner_id, id),
    FOREIGN KEY (owner_id, run_id, revision_id) REFERENCES paperlens_m1.input_revisions
);

CREATE TABLE paperlens_m1.passages (
    owner_id text NOT NULL,
    bundle_id uuid NOT NULL,
    id uuid NOT NULL,
    payload jsonb NOT NULL,
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', payload->>'text')) STORED,
    embedding vector(384),
    PRIMARY KEY (owner_id, bundle_id, id),
    FOREIGN KEY (owner_id, bundle_id) REFERENCES paperlens_m1.bundles
);

CREATE INDEX passages_fts ON paperlens_m1.passages USING gin (search_vector);
CREATE INDEX passages_cosine ON paperlens_m1.passages USING hnsw (embedding vector_cosine_ops);

CREATE TABLE paperlens_m1.findings (
    owner_id text NOT NULL,
    bundle_id uuid NOT NULL,
    id uuid NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY (owner_id, bundle_id, id),
    FOREIGN KEY (owner_id, bundle_id) REFERENCES paperlens_m1.bundles
);

CREATE TABLE paperlens_m1.reports (
    owner_id text NOT NULL,
    bundle_id uuid NOT NULL,
    id uuid NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    payload jsonb NOT NULL,
    PRIMARY KEY (owner_id, bundle_id, id),
    UNIQUE (owner_id, bundle_id, version),
    FOREIGN KEY (owner_id, bundle_id) REFERENCES paperlens_m1.bundles
);

CREATE FUNCTION paperlens_m1.reject_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'M1 evidence records are append-only';
END;
$$;

CREATE TRIGGER frozen_bundle BEFORE UPDATE OR DELETE ON paperlens_m1.bundles
FOR EACH ROW EXECUTE FUNCTION paperlens_m1.reject_mutation();

CREATE TRIGGER frozen_passage BEFORE UPDATE OR DELETE ON paperlens_m1.passages
FOR EACH ROW EXECUTE FUNCTION paperlens_m1.reject_mutation();

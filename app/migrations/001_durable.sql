-- Applied by the local database owner, never an application credential.
CREATE TABLE IF NOT EXISTS jobs (
    run_id uuid PRIMARY KEY,
    data jsonb NOT NULL,
    status text NOT NULL CHECK (status IN
        ('queued', 'running', 'awaiting_approval', 'completed', 'failed')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    deadline timestamptz NOT NULL,
    lease_until timestamptz,
    lease_token uuid,
    attempts integer NOT NULL DEFAULT 0,
    step_count integer NOT NULL DEFAULT 0,
    max_steps integer NOT NULL CHECK (max_steps BETWEEN 1 AND 20),
    max_attempts integer NOT NULL CHECK (max_attempts BETWEEN 1 AND 10)
);
CREATE INDEX IF NOT EXISTS jobs_claim ON jobs (status, created_at);
CREATE TABLE IF NOT EXISTS events (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES jobs,
    at timestamptz NOT NULL DEFAULT clock_timestamp(),
    kind text NOT NULL,
    detail jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
    approval_id uuid PRIMARY KEY,
    run_id uuid NOT NULL UNIQUE REFERENCES jobs,
    tool text NOT NULL,
    arguments jsonb NOT NULL,
    approved_by text NOT NULL,
    expires_at timestamptz NOT NULL,
    consumed_key text
);
CREATE TABLE IF NOT EXISTS tool_results (
    idempotency_key text PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES jobs,
    tool text NOT NULL,
    arguments jsonb NOT NULL,
    result jsonb NOT NULL
);
-- The entire simulated effect lives in this database. It is not a real restart.
CREATE TABLE IF NOT EXISTS orders_state (
    run_id uuid PRIMARY KEY REFERENCES jobs,
    restart_count integer NOT NULL DEFAULT 0
);
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO lab_api, lab_worker, lab_tools;
GRANT SELECT, INSERT ON jobs TO lab_api;
GRANT UPDATE (status, data, deadline) ON jobs TO lab_api;
GRANT SELECT, INSERT ON approvals TO lab_api;
GRANT SELECT ON events TO lab_api;
GRANT SELECT, UPDATE ON jobs TO lab_worker;
GRANT SELECT, INSERT ON events TO lab_worker;
GRANT USAGE ON SEQUENCE events_event_id_seq TO lab_worker;
GRANT SELECT ON approvals TO lab_worker;
GRANT SELECT ON jobs TO lab_tools;
GRANT SELECT, UPDATE (consumed_key) ON approvals TO lab_tools;
GRANT SELECT, INSERT ON tool_results TO lab_tools;
GRANT SELECT, INSERT, UPDATE ON orders_state TO lab_tools;

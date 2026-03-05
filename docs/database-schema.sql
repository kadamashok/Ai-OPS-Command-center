# Database Schema (PostgreSQL)

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE incidents (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  transaction_id VARCHAR(100),
  source_system VARCHAR(50) NOT NULL,
  severity VARCHAR(20) NOT NULL,
  status VARCHAR(30) NOT NULL,
  title VARCHAR(200) NOT NULL,
  root_cause VARCHAR(300),
  detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at TIMESTAMPTZ,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_incidents_status ON incidents(status);
CREATE INDEX idx_incidents_detected_at ON incidents(detected_at DESC);

CREATE TABLE diagnostics (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
  check_type VARCHAR(50) NOT NULL,
  check_result VARCHAR(20) NOT NULL,
  latency_ms INTEGER,
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_diagnostics_incident_id ON diagnostics(incident_id);

CREATE TABLE runbook_executions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  incident_id UUID NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
  runbook_name VARCHAR(120) NOT NULL,
  action_name VARCHAR(120) NOT NULL,
  executor_type VARCHAR(20) NOT NULL,
  status VARCHAR(20) NOT NULL,
  output TEXT,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ
);

CREATE INDEX idx_runbook_exec_incident_id ON runbook_executions(incident_id);

CREATE TABLE recovery_queue (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  transaction_id VARCHAR(100) NOT NULL,
  flow_type VARCHAR(50) NOT NULL,
  payload JSONB NOT NULL,
  dedup_key VARCHAR(140) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'queued',
  retry_count INTEGER NOT NULL DEFAULT 0,
  max_retries INTEGER NOT NULL DEFAULT 10,
  next_retry_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX uq_recovery_dedup_key ON recovery_queue(dedup_key);
CREATE INDEX idx_recovery_status_next_retry ON recovery_queue(status, next_retry_at);

CREATE TABLE transaction_events (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  transaction_id VARCHAR(100) NOT NULL,
  flow_type VARCHAR(50) NOT NULL,
  step_name VARCHAR(80) NOT NULL,
  system_name VARCHAR(50) NOT NULL,
  status VARCHAR(20) NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_txn_events_transaction_id ON transaction_events(transaction_id);
CREATE INDEX idx_txn_events_observed_at ON transaction_events(observed_at DESC);

CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  actor VARCHAR(120) NOT NULL,
  action VARCHAR(120) NOT NULL,
  resource VARCHAR(120) NOT NULL,
  result VARCHAR(30) NOT NULL,
  correlation_id VARCHAR(100),
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);
```

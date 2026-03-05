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

CREATE TABLE incident_patterns (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  service VARCHAR(80) NOT NULL,
  error_type VARCHAR(80) NOT NULL,
  pattern_key VARCHAR(120) NOT NULL UNIQUE,
  severity VARCHAR(20) NOT NULL,
  probable_root_cause VARCHAR(300) NOT NULL,
  default_runbook VARCHAR(120) NOT NULL,
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_incident_patterns_service_error ON incident_patterns(service, error_type);
CREATE INDEX idx_incident_patterns_pattern_key ON incident_patterns(pattern_key);

CREATE TABLE runbooks (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  runbook_name VARCHAR(120) NOT NULL UNIQUE,
  description VARCHAR(300) NOT NULL,
  requires_role VARCHAR(40) NOT NULL DEFAULT 'operator',
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  verification_policy JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_runbooks_enabled ON runbooks(enabled);

CREATE TABLE automation_actions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  incident_id UUID NOT NULL,
  runbook_name VARCHAR(120) NOT NULL,
  trigger VARCHAR(200) NOT NULL,
  executed_by VARCHAR(120) NOT NULL,
  status VARCHAR(20) NOT NULL,
  details JSONB NOT NULL DEFAULT '{}'::jsonb,
  executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_automation_actions_incident_id ON automation_actions(incident_id);
CREATE INDEX idx_automation_actions_executed_at ON automation_actions(executed_at DESC);

CREATE TABLE incident_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  incident_id UUID NOT NULL,
  service VARCHAR(80) NOT NULL,
  error_type VARCHAR(80) NOT NULL,
  root_cause VARCHAR(300) NOT NULL,
  action_taken VARCHAR(120) NOT NULL,
  status VARCHAR(30) NOT NULL,
  resolution_time_seconds DOUBLE PRECISION,
  report_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_incident_history_incident_id ON incident_history(incident_id);
CREATE INDEX idx_incident_history_service_error ON incident_history(service, error_type);
```

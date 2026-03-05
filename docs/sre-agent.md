# AI SRE Agent Microservice

## Purpose

`sre-agent` is the secure decision engine between diagnostics and automation in CAROP.

Workflow:
`Event -> Diagnostics -> AI SRE Agent -> Runbook Execution -> Verification -> Incident Closed`

## Responsibilities

1. Incident Analyzer
- Parses diagnostic payloads.
- Computes severity and pattern keys such as `OMS_API_TIMEOUT`.

2. Incident Knowledge Base
- Tables:
  - `incident_patterns`
  - `runbooks`
  - `automation_actions`
  - `incident_history`
- Seeds default rule mappings on startup.

3. Runbook Decision Engine
- Rule-based selection now.
- Cache-backed lookups using Redis.
- Designed for future ML replacement behind the same interface.

4. Runbook Executor
- Calls `automation-engine` and `runbook-executor`.
- Logs all automated actions in `automation_actions` and `audit_logs`.

5. Verification Engine
- Validates recovery using:
  - dashboard KPIs
  - transaction-monitor incident normalization
- Executes secondary runbook when primary remediation does not recover.

6. Incident Reporter
- Persists machine-readable reports into `incident_history`.

## Security Controls

- JWT auth on all APIs.
- RBAC enforced (`operator` for execute/analyze, `admin` for governance toggles).
- Input validation via Pydantic schemas.
- Rate limiting middleware (Redis-backed, local fallback).
- Security headers, strict CORS policy from shared middleware.
- Audit logging for every automated action and governance change.
- SQL injection resistance via SQLAlchemy ORM parameterization.
- Runbook governance: enable/disable catalog with admin-only control.

## APIs

- `POST /incident/analyze`
- `POST /runbook/execute`
- `GET /incident/history`
- `GET /runbook/catalog`
- `PATCH /runbook/catalog/{runbook_name}`

## Runtime Dependencies

- Kafka (`carop.rca.completed`)
- PostgreSQL
- Redis
- diagnostics-engine
- automation-engine
- runbook-executor
- transaction-monitor
- incident-service

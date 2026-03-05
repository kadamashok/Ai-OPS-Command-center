# Backend Microservices Structure

```
backend/
  libs/common/carop_common/
    config.py
    security.py
    events.py
    db.py
    models.py
    web.py
  services/
    api-gateway/app/main.py
    transaction-monitor/app/main.py
    diagnostic-engine/app/main.py
    automation-engine/app/main.py
    runbook-executor/app/main.py
    runbook-executor/app/runbook_engine.py
    replay-engine/app/main.py
    incident-service/app/main.py
    dashboard-service/app/main.py
    orchestrator/app/main.py
    sre-agent/app/main.py
    sre-agent/app/incident_analyzer.py
    sre-agent/app/decision_engine.py
    sre-agent/app/runbook_executor.py
    sre-agent/app/verification_engine.py
    sre-agent/app/security.py
```

## Service contracts

- `api-gateway`: authn/authz, RBAC guard, security headers, rate limiting.
- `transaction-monitor`: receives transaction step events and raises incidents.
- `diagnostic-engine`: executes RCA checks and emits probable root cause.
- `automation-engine`: authorizes and dispatches remediation executions.
- `runbook-executor`: loads YAML runbooks and executes action adapters.
- `replay-engine`: queues and replays failed business transactions.
- `incident-service`: incident state and status lifecycle.
- `dashboard-service`: aggregates KPI and incident views for UI.
- `orchestrator`: Kafka consumer that triggers diagnostics and recovery queueing.
- `sre-agent`: AI SRE decision service that maps diagnostic patterns to runbooks, executes remediation, verifies outcome, and writes incident reports.

## Cross-cutting concerns

- Shared security middleware and token validation in `carop_common/security.py`.
- Secure headers and CORS configuration in `carop_common/web.py`.
- Pydantic contracts in `carop_common/models.py`.
- Shared SQLAlchemy schema/session in `carop_common/db.py`.

# CAROP System Architecture

## Enterprise Context

CAROP continuously monitors retail transaction chains and automatically recovers operations.

### Business flows

1. Online order flow: `Customer -> croma.com -> OMS -> WMS -> SAP -> Dispatch`
2. Store billing flow: `Customer -> Cloud MPOS -> OMS -> WMS -> SAP`
3. Inventory flow: `WMS -> OMS -> croma.com -> MPOS`

## Architecture Diagram

```mermaid
flowchart LR
    subgraph Channels
      CUS[Customer]
      WEB[croma.com]
      MPOS[Cloud MPOS]
    end

    subgraph CoreRetail
      OMS[OMS]
      WMS[WMS]
      SAP[SAP]
      PG[Payment Gateway]
      DISP[Dispatch]
    end

    subgraph CAROP
      APIGW[API Gateway]
      TM[Transaction Monitor]
      DE[Diagnostic Engine]
      SRE[AI SRE Agent]
      IS[Incident Service]
      AE[Automation Engine]
      RE[Runbook Executor]
      RPE[Replay Engine]
      DS[Dashboard Service]
      KAFKA[(Kafka Event Bus)]
      PGSQL[(PostgreSQL)]
      ES[(Elasticsearch)]
      PROM[(Prometheus)]
      OTEL[OpenTelemetry Collector]
    end

    CUS --> WEB
    CUS --> MPOS
    WEB --> OMS
    MPOS --> OMS
    OMS --> WMS --> SAP --> DISP
    WEB --> PG

    OMS -. events .-> TM
    WMS -. events .-> TM
    SAP -. events .-> TM
    PG -. events .-> TM

    APIGW --> TM
    TM --> KAFKA
    TM --> IS

    KAFKA --> DE
    DE --> IS
    DE --> SRE
    SRE --> AE

    AE --> RE
    RE --> KAFKA
    RE --> IS

    TM --> RPE
    RPE --> KAFKA
    RPE --> IS

    DS --> PGSQL
    DS --> ES
    DS --> PROM

    TM --> OTEL
    DE --> OTEL
    SRE --> OTEL
    AE --> OTEL
    RE --> OTEL
    RPE --> OTEL
    IS --> OTEL
    DS --> OTEL

    IS --> PGSQL
    TM --> PGSQL
    DE --> PGSQL
    RPE --> PGSQL
    IS --> ES
```

## Detect -> Diagnose -> Auto Fix -> Recovery Sequence

1. `transaction-monitor` detects flow anomaly or SLA breach.
2. Event emitted to Kafka topic `carop.anomaly.detected`.
3. `diagnostic-engine` runs health probes (API, DB, queue, k8s, auth, network).
4. Root cause event emitted to `carop.rca.completed`.
5. `sre-agent` analyzes incident pattern and selects runbook from KB.
6. `sre-agent` triggers `automation-engine` and `runbook-executor`.
7. `sre-agent` verifies recovery and optionally executes secondary runbook.
8. `replay-engine` replays failed transactions from recovery queue.
9. `incident-service` tracks state transitions and audit evidence.
10. `dashboard-service` exposes real-time status for command center.

## Service Responsibilities

- API Gateway: JWT/OAuth2 validation, RBAC, rate limiting, request signing.
- Transaction Monitor: transaction graph correlation and KPI/SLO monitoring.
- Diagnostic Engine: deterministic checks + heuristic scoring for root cause.
- AI SRE Agent: incident analysis, rule-based runbook decision, remediation orchestration, verification and reporting.
- Automation Engine: policy guardrails, action approvals, blast-radius limits.
- Runbook Executor: pluggable action adapters (`k8s`, `ansible`, `ssh`, `http-retry`, `queue-replay`).
- Replay Engine: idempotent retry pipeline with backoff and deduplication keys.
- Incident Service: incident state machine + compliance audit log.
- Dashboard Service: health, incidents, metrics aggregation for React UI.

## Non-functional Requirements

- HA with horizontal scaling and stateless service design.
- Exactly-once semantic approximations using idempotency keys.
- MTTR optimization with automated remediation and replay.
- Full traceability using OpenTelemetry + structured audit logs.


## Autonomous Orchestration

CAROP includes an `orchestrator` + `sre-agent` workflow for closed-loop automation:

1. Consume `carop.anomaly.detected` and call Diagnostic Engine.
2. Queue failed transaction in Replay Engine.
3. `sre-agent` consumes `carop.rca.completed` and selects remediation runbook.
4. `sre-agent` triggers Automation Engine + Runbook Executor.
5. `sre-agent` verifies recovery and writes incident report + audit trail.

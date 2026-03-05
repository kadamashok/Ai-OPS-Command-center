# Croma Autonomous Retail Operations Platform (CAROP)

Developed by Ashok Kadam using AI with guidance from Swarup.

CAROP is a production-oriented, event-driven, self-healing enterprise platform for retail operations.

Core loop:
`DETECT -> DIAGNOSE -> AUTO FIX -> TRANSACTION RECOVERY`

## Current Project Status

- `Status`: Running locally with Docker Compose on non-conflicting host ports (`38000+` range).
- `Architecture`: Microservices + Kafka event orchestration + PostgreSQL persistence.
- `Security`: OWASP ASVS-aligned controls implemented in API/middleware/CI.
- `Automation`: Runbook-driven remediation engine with Kubernetes/Ansible/SSH action adapters.
- `Validation`: Integration flow test and synthetic transaction simulation available.

## Business Scope

CAROP monitors and heals cross-platform retail flows across:

- SAP
- OMS
- WMS
- croma.com eCommerce
- Cloud MPOS
- Payment gateways
- Kubernetes/container platform
- Databases
- Message queues
- Enterprise APIs/microservices

## Platform Capabilities

- End-to-end business transaction monitoring
- Root cause analysis (API, DB, queue, infra, auth, network checks)
- Self-healing remediation (restart/scale/failover/retry/replay)
- Transaction recovery queue and replay engine
- Runbook library for common operational incidents
- Real-time command center dashboard
- Event-driven autonomous orchestrator

## Tech Stack

- Backend: `Python`, `FastAPI`, `SQLAlchemy`
- Frontend: `React`, `TypeScript`, `Vite`
- Event Streaming: `Kafka`
- Storage: `PostgreSQL` (plus docs for Elasticsearch integration)
- Observability: `Prometheus`, `OpenTelemetry`
- Automation: `Ansible`, `Kubernetes API`, `SSH`
- Deployment: `Docker`, `Kubernetes`
- DevSecOps: `GitHub Actions`, `Bandit`, `Semgrep`, `pip-audit`, `npm audit`, `Trivy`, `Gitleaks`

## Repository Structure

- `backend/` microservices + shared libraries
- `frontend/dashboard/` command center UI
- `infra/docker/` compose and Dockerfiles
- `infra/k8s/` base and security manifests
- `infra/ansible/` runbooks and inventory
- `docs/` architecture, APIs, schema, security, installation
- `.github/workflows/` CI/CD and security automation

## Services and Ports (Host)

- API Gateway: `http://localhost:38000`
- Transaction Monitor: `http://localhost:38001`
- Diagnostic Engine: `http://localhost:38002`
- Automation Engine: `http://localhost:38003`
- Replay Engine: `http://localhost:38004`
- Runbook Executor: `http://localhost:38005`
- Dashboard Service: `http://localhost:38006`
- Incident Service: `http://localhost:38007`
- Orchestrator: `http://localhost:38008`
- Dashboard UI: `http://localhost:35173`
- Prometheus: `http://localhost:39090`

## Quick Start

```bash
docker compose -f infra/docker/docker-compose.yml up --build -d
```

## Documentation

- [Architecture](docs/architecture.md)
- [API Spec](docs/api-spec.yaml)
- [Database Schema](docs/database-schema.sql)
- [Security Controls](docs/security-controls.md)
- [Installation Guide](docs/installation-guide.md)

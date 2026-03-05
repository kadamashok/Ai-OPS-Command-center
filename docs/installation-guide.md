# Installation Guide

## Prerequisites

- Docker 24+
- Kubernetes 1.29+
- Python 3.11+
- Node.js 20+

## 1. Clone and configure

```bash
git clone <repo>
cd carop
cp .env.example .env
```

## 2. Local development (Docker Compose)

```bash
docker compose -f infra/docker/docker-compose.yml up --build -d
```

Endpoints:

- API Gateway: `http://localhost:38000`
- Transaction Monitor: `http://localhost:38001`
- Diagnostic Engine: `http://localhost:38002`
- Automation Engine: `http://localhost:38003`
- Replay Engine: `http://localhost:38004`
- Runbook Executor: `http://localhost:38005`
- Dashboard Service: `http://localhost:38006`
- Incident Service: `http://localhost:38007`
- Orchestrator: `http://localhost:38008`
- AI SRE Agent: `http://localhost:38009`
- Dashboard UI: `http://localhost:35173`
- Redis: `localhost:36379`

## 3. Backend local run (without Docker)

```bash
cd backend
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start any service from its `app` folder:

```powershell
cd services\transaction-monitor\app
$env:PYTHONPATH='../../../../libs/common'
$env:POSTGRES_DSN='postgresql://carop:carop@localhost:5432/carop'
uvicorn main:app --reload --port 8001
```

## 4. Frontend setup

```bash
cd frontend/dashboard
npm install
npm run dev
```

## 5. Integration tests

```bash
cd backend
pytest -q tests/test_e2e_simulation.py
```

## 6. Synthetic transaction simulation

```bash
cd backend
python tools/simulate_transactions.py --count 50 --failure-rate 0.3
```

## 7. Kubernetes deployment

```bash
kubectl apply -f infra/k8s/security
kubectl apply -f infra/k8s/base
```

## 8. Security verification checklist

- Validate HSTS/CSP headers through ingress/API gateway.
- Confirm all containers run as non-root.
- Confirm network policy deny-by-default posture.
- Execute SAST/DAST/dependency/container scans in CI.

## 9. Production rollout notes

- Integrate external secrets manager and key rotation.
- Enable mTLS/service mesh for east-west traffic.
- Configure HPA and SLO-based alerting.
- Export audit logs to enterprise SIEM.

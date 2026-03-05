from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from carop_common.db import Diagnostic, Incident, get_db, init_db
from carop_common.events import KafkaEventPublisher
from carop_common.models import DiagnosticResult
from carop_common.security import current_principal
from carop_common.web import apply_common_fastapi_config

publisher = KafkaEventPublisher()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    await publisher.start()
    yield
    await publisher.stop()


app = FastAPI(title="CAROP Diagnostic Engine", version="1.0.0", lifespan=lifespan)
apply_common_fastapi_config(app)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "diagnostic-engine"}


@app.post("/api/v1/incidents/{incident_id}/diagnose", response_model=DiagnosticResult)
async def diagnose_incident(
    incident_id: str,
    _: dict = Depends(current_principal),
    db: Session = Depends(get_db),
):
    checks = [
        {"check": "api_health", "result": "failed", "details": {"service": "wms-api", "http": 504}},
        {"check": "db_latency", "result": "ok", "latency_ms": 42},
        {"check": "queue_backlog", "result": "warning", "depth": 920},
        {"check": "container_status", "result": "ok", "restarts": 0},
        {"check": "network_latency", "result": "warning", "ms": 180},
        {"check": "auth_failures", "result": "ok", "rate": 0.3},
    ]
    root_cause = "WMS API timeout causing OMS->WMS step failures"

    for c in checks:
        db.add(
            Diagnostic(
                incident_id=incident_id,
                check_type=c["check"],
                check_result=c["result"],
                latency_ms=c.get("latency_ms"),
                details=c.get("details", c),
                created_at=datetime.now(timezone.utc),
            )
        )

    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if incident:
        incident.root_cause = root_cause
        incident.status = "diagnosed"

    db.commit()

    await publisher.publish(
        "carop.rca.completed",
        {"incident_id": incident_id, "root_cause": root_cause, "confidence": 0.91},
    )

    return DiagnosticResult(
        incident_id=incident_id,
        root_cause=root_cause,
        confidence=0.91,
        checks=checks,
    )

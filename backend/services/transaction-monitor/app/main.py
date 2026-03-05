from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from carop_common.db import Incident, TransactionEvent as TxEventRow, get_db, init_db
from carop_common.events import KafkaEventPublisher
from carop_common.models import IncidentCreate, TransactionEvent
from carop_common.security import current_principal
from carop_common.web import apply_common_fastapi_config

publisher = KafkaEventPublisher()


def _suggest_runbook(system_name: str) -> str:
    system = system_name.lower()
    if "wms" in system:
        return "wms_api_timeout"
    if "sap" in system:
        return "sap_queue_stuck"
    if "oms" in system:
        return "oms_service_crash"
    if "mpos" in system:
        return "mpos_sync_failure"
    return "db_pool_exhaustion"


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    await publisher.start()
    yield
    await publisher.stop()


app = FastAPI(title="CAROP Transaction Monitor", version="1.0.0", lifespan=lifespan)
apply_common_fastapi_config(app)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "transaction-monitor"}


@app.post("/api/v1/transactions/events")
async def ingest_event(
    event: TransactionEvent,
    _: dict = Depends(current_principal),
    db: Session = Depends(get_db),
):
    row = TxEventRow(
        transaction_id=event.transaction_id,
        flow_type=event.flow_type,
        step_name=event.step_name,
        system_name=event.system_name,
        status=event.status,
        payload=event.payload,
        observed_at=datetime.now(timezone.utc),
    )
    db.add(row)

    incident_payload = None
    if event.status == "failed":
        incident = Incident(
            transaction_id=event.transaction_id,
            source_system=event.system_name,
            severity="high",
            status="detected",
            title=f"Failure at step {event.step_name}",
            metadata_json={
                "flow": event.flow_type,
                "payload": event.payload,
                "suggested_runbook": _suggest_runbook(event.system_name),
            },
            detected_at=datetime.now(timezone.utc),
        )
        db.add(incident)
        db.flush()
        incident_payload = {
            "id": incident.id,
            "transaction_id": incident.transaction_id,
            "source_system": incident.source_system,
            "severity": incident.severity,
            "status": incident.status,
            "title": incident.title,
            "detected_at": incident.detected_at.isoformat(),
            "flow_type": event.flow_type,
            "payload": event.payload,
            "suggested_runbook": incident.metadata_json.get("suggested_runbook"),
        }

    db.commit()

    event_payload = {
        "transaction_id": event.transaction_id,
        "flow_type": event.flow_type,
        "step": event.step_name,
        "system": event.system_name,
        "status": event.status,
    }
    await publisher.publish("carop.transaction.events", event_payload)

    if incident_payload:
        await publisher.publish("carop.anomaly.detected", incident_payload)
        return {"status": "incident_created", "incident": incident_payload}

    return {"status": "event_recorded"}


@app.post("/api/v1/incidents")
async def create_incident(
    req: IncidentCreate,
    _: dict = Depends(current_principal),
    db: Session = Depends(get_db),
):
    incident = Incident(
        transaction_id=req.transaction_id,
        source_system=req.source_system,
        severity=req.severity,
        status="detected",
        title=req.title,
        metadata_json=req.metadata,
        detected_at=datetime.now(timezone.utc),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return {
        "id": incident.id,
        "transaction_id": incident.transaction_id,
        "source_system": incident.source_system,
        "severity": incident.severity,
        "status": incident.status,
        "title": incident.title,
        "detected_at": incident.detected_at.isoformat(),
    }


@app.get("/api/v1/incidents")
async def list_incidents(_: dict = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.query(Incident).order_by(Incident.detected_at.desc()).limit(100).all()
    return {
        "items": [
            {
                "id": i.id,
                "transaction_id": i.transaction_id,
                "source_system": i.source_system,
                "severity": i.severity,
                "status": i.status,
                "title": i.title,
                "root_cause": i.root_cause,
                "detected_at": i.detected_at.isoformat(),
            }
            for i in rows
        ]
    }

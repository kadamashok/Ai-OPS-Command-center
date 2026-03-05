from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from carop_common.db import Incident, get_db, init_db
from carop_common.security import current_principal, require_role
from carop_common.web import apply_common_fastapi_config


class IncidentUpdate(BaseModel):
    status: str
    root_cause: str | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="CAROP Incident Service", version="1.0.0", lifespan=lifespan)
apply_common_fastapi_config(app)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "incident-service"}


@app.get("/api/v1/incidents")
async def list_incidents(_: dict = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.query(Incident).order_by(Incident.detected_at.desc()).limit(100).all()
    return {
        "items": [
            {
                "id": i.id,
                "transaction_id": i.transaction_id,
                "status": i.status,
                "severity": i.severity,
                "title": i.title,
                "root_cause": i.root_cause,
                "detected_at": i.detected_at.isoformat(),
            }
            for i in rows
        ]
    }


@app.post("/api/v1/incidents")
async def create_incident(payload: dict, _: dict = Depends(require_role("operator")), db: Session = Depends(get_db)):
    incident = Incident(
        transaction_id=payload.get("transaction_id"),
        source_system=payload.get("source_system", "unknown"),
        severity=payload.get("severity", "medium"),
        status="detected",
        title=payload.get("title", "Incident created"),
        metadata_json=payload.get("metadata", {}),
        detected_at=datetime.now(timezone.utc),
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return {
        "id": incident.id,
        "status": incident.status,
        "severity": incident.severity,
        "title": incident.title,
        "detected_at": incident.detected_at.isoformat(),
    }


@app.patch("/api/v1/incidents/{incident_id}")
async def update_incident(
    incident_id: str,
    req: IncidentUpdate,
    _: dict = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.status = req.status
    if req.root_cause:
        incident.root_cause = req.root_cause
    if req.status == "resolved":
        incident.resolved_at = datetime.now(timezone.utc)

    db.commit()
    return {
        "id": incident.id,
        "status": incident.status,
        "root_cause": incident.root_cause,
        "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
    }

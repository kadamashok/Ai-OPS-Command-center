from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI
from sqlalchemy.orm import Session

from carop_common.db import Incident, RunbookExecution, get_db, init_db
from carop_common.events import KafkaEventPublisher
from carop_common.models import AutomationRequest
from carop_common.security import current_principal, require_role
from carop_common.web import apply_common_fastapi_config

publisher = KafkaEventPublisher()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    await publisher.start()
    yield
    await publisher.stop()


app = FastAPI(title="CAROP Automation Engine", version="1.0.0", lifespan=lifespan)
apply_common_fastapi_config(app)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "automation-engine"}


@app.post("/api/v1/automation/execute")
async def execute_automation(
    req: AutomationRequest,
    _: dict = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    execution = RunbookExecution(
        incident_id=req.incident_id,
        runbook_name=req.runbook_name,
        action_name="dispatch_runbook",
        executor_type="runbook-executor",
        status="running",
        output="Runbook dispatch queued",
        started_at=datetime.now(timezone.utc),
    )
    db.add(execution)

    incident = db.query(Incident).filter(Incident.id == req.incident_id).first()
    if incident:
        incident.status = "auto-fix-running"

    db.commit()
    db.refresh(execution)

    await publisher.publish(
        "carop.automation.requested",
        {
            "incident_id": req.incident_id,
            "runbook_name": req.runbook_name,
            "parameters": req.parameters,
            "execution_id": execution.id,
        },
    )

    return {
        "status": "accepted",
        "execution": {
            "id": execution.id,
            "incident_id": execution.incident_id,
            "runbook_name": execution.runbook_name,
            "status": execution.status,
            "started_at": execution.started_at.isoformat(),
            "parameters": req.parameters,
        },
    }


@app.get("/api/v1/automation/executions")
async def list_executions(_: dict = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.query(RunbookExecution).order_by(RunbookExecution.started_at.desc()).limit(100).all()
    return {
        "items": [
            {
                "id": r.id,
                "incident_id": r.incident_id,
                "runbook_name": r.runbook_name,
                "status": r.status,
                "started_at": r.started_at.isoformat(),
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in rows
        ]
    }

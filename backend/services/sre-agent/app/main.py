from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Literal

from aiokafka import AIOKafkaConsumer
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from carop_common.db import AuditLog, IncidentHistory, get_db, init_db
from carop_common.security import current_principal, require_role
from carop_common.web import apply_common_fastapi_config

from decision_engine import DecisionEngine
from incident_analyzer import IncidentAnalyzer
from runbook_executor import RunbookExecutor
from security import apply_sre_security
from verification_engine import VerificationEngine


class IncidentAnalyzeRequest(BaseModel):
    incident_id: str = Field(min_length=3, max_length=80)
    service: str = Field(min_length=2, max_length=80)
    error_type: str = Field(min_length=3, max_length=80)
    latency_ms: int = Field(ge=0, le=300000)
    timestamp: str | None = None
    root_cause: str | None = None
    context: dict = Field(default_factory=dict)


class RunbookExecuteRequest(BaseModel):
    incident_id: str = Field(min_length=3, max_length=80)
    runbook_name: str = Field(min_length=3, max_length=120)
    trigger: str = Field(min_length=3, max_length=200)
    parameters: dict = Field(default_factory=dict)


class RunbookToggleRequest(BaseModel):
    enabled: bool


class SreAgentService:
    def __init__(self) -> None:
        self.bootstrap = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
        self.group_id = os.getenv("SRE_AGENT_GROUP_ID", "carop-sre-agent-v1")
        self.analyzer = IncidentAnalyzer()
        self.decision_engine = DecisionEngine()
        self.executor = RunbookExecutor()
        self.verifier = VerificationEngine()
        self.sre_actor = "AI_SRE_AGENT"

    async def consume_diagnostic_events(self, stop_event: asyncio.Event) -> None:
        consumer = AIOKafkaConsumer(
            "carop.rca.completed",
            bootstrap_servers=self.bootstrap,
            group_id=self.group_id,
            enable_auto_commit=True,
            auto_offset_reset="latest",
        )
        try:
            await consumer.start()
        except Exception:
            return

        try:
            while not stop_event.is_set():
                batch = await consumer.getmany(timeout_ms=1000, max_records=20)
                for _, messages in batch.items():
                    for msg in messages:
                        payload = json.loads(msg.value.decode("utf-8"))
                        await self._handle_rca_event(payload)
        finally:
            await consumer.stop()

    async def _handle_rca_event(self, payload: dict[str, Any]) -> None:
        incident_id = str(payload.get("incident_id", "")).strip()
        if not incident_id:
            return

        service, error_type = self._infer_service_error_type(payload.get("root_cause", ""))
        req = IncidentAnalyzeRequest(
            incident_id=incident_id,
            service=service,
            error_type=error_type,
            latency_ms=int(payload.get("latency_ms", 0) or 0),
            root_cause=payload.get("root_cause"),
            context={"source": "kafka_rca_event"},
        )
        db = next(get_db())
        try:
            await self.process_incident(db=db, req=req, principal={"sub": self.sre_actor, "roles": ["admin"]})
        finally:
            db.close()

    async def process_incident(self, db: Session, req: IncidentAnalyzeRequest, principal: dict) -> dict[str, Any]:
        started = datetime.now(timezone.utc)
        analysis = self.analyzer.analyze(req.model_dump())
        decision = self.decision_engine.select_runbook(
            db=db,
            service=analysis["service"],
            error_type=analysis["error_type"],
            pattern_key=analysis["pattern_key"],
        )
        if not decision.get("enabled", True):
            raise HTTPException(status_code=403, detail="Selected runbook is disabled")

        execution = await self.executor.execute(
            db=db,
            incident_id=req.incident_id,
            runbook_name=decision["runbook_name"],
            trigger=f"{analysis['service']} {analysis['error_type']} pattern",
            params={"latency_ms": req.latency_ms, **req.context},
        )

        verification = await self.verifier.verify(incident_id=req.incident_id, service=analysis["service"])
        secondary = None
        if not verification["verified"]:
            secondary_runbook = "scale_kubernetes"
            secondary = await self.executor.execute(
                db=db,
                incident_id=req.incident_id,
                runbook_name=secondary_runbook,
                trigger="secondary_remediation_after_verification_failure",
                params={"primary_runbook": decision["runbook_name"]},
            )
            verification = await self.verifier.verify(incident_id=req.incident_id, service=analysis["service"])

        ended = datetime.now(timezone.utc)
        resolution_seconds = (ended - started).total_seconds()
        status: Literal["resolved", "mitigated", "failed"] = (
            "resolved" if verification["verified"] else ("mitigated" if execution["status"] == "success" else "failed")
        )

        report = {
            "incident_id": req.incident_id,
            "service": analysis["service"],
            "error_type": analysis["error_type"],
            "root_cause": analysis["probable_root_cause"],
            "action_taken": decision["runbook_name"],
            "secondary_action": secondary["details"]["runbook_name"] if secondary else None,
            "resolution_time_seconds": resolution_seconds,
            "status": status,
            "verification": verification,
            "timestamp": ended.isoformat(),
        }

        db.add(
            IncidentHistory(
                incident_id=req.incident_id,
                service=analysis["service"],
                error_type=analysis["error_type"],
                root_cause=analysis["probable_root_cause"],
                action_taken=decision["runbook_name"],
                status=status,
                resolution_time_seconds=resolution_seconds,
                report_json=report,
                created_at=ended,
            )
        )
        db.add(
            AuditLog(
                actor=str(principal.get("sub", self.sre_actor)),
                action="incident_analyze_and_remediate",
                resource=f"incident:{req.incident_id}",
                result=status,
                correlation_id=req.incident_id,
                details=report,
                created_at=ended,
            )
        )
        db.commit()
        return report

    def _infer_service_error_type(self, root_cause: str) -> tuple[str, str]:
        rc = root_cause.lower()
        if "oms" in rc and "timeout" in rc:
            return ("OMS", "API_TIMEOUT")
        if "wms" in rc and "timeout" in rc:
            return ("WMS", "API_TIMEOUT")
        if "sap" in rc and "queue" in rc:
            return ("SAP", "QUEUE_STUCK")
        if "mpos" in rc:
            return ("MPOS", "SERVICE_UNAVAILABLE")
        return ("OMS", "SERVICE_UNAVAILABLE")

sre_service = SreAgentService()
stop_event = asyncio.Event()
consumer_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global consumer_task
    init_db()
    db = next(get_db())
    try:
        sre_service.decision_engine.seed_knowledge_base(db)
    finally:
        db.close()
    consumer_task = asyncio.create_task(sre_service.consume_diagnostic_events(stop_event))
    yield
    stop_event.set()
    if consumer_task:
        await consumer_task


app = FastAPI(title="CAROP AI SRE Agent", version="1.0.0", lifespan=lifespan)
apply_common_fastapi_config(app)
apply_sre_security(app)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "sre-agent"}


@app.post("/incident/analyze")
async def analyze_incident(
    req: IncidentAnalyzeRequest,
    principal: dict = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    return await sre_service.process_incident(db=db, req=req, principal=principal)


@app.post("/runbook/execute")
async def execute_runbook(
    req: RunbookExecuteRequest,
    _: dict = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    return await sre_service.executor.execute(
        db=db,
        incident_id=req.incident_id,
        runbook_name=req.runbook_name,
        trigger=req.trigger,
        params=req.parameters,
    )


@app.get("/incident/history")
async def incident_history(
    service: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _: dict = Depends(current_principal),
    db: Session = Depends(get_db),
):
    q = db.query(IncidentHistory)
    if service:
        q = q.filter(IncidentHistory.service == service.upper())
    rows = q.order_by(IncidentHistory.created_at.desc()).limit(limit).all()
    return {"items": [x.report_json for x in rows]}


@app.get("/runbook/catalog")
async def runbook_catalog(_: dict = Depends(current_principal), db: Session = Depends(get_db)):
    return {"items": sre_service.decision_engine.runbook_catalog(db)}


@app.patch("/runbook/catalog/{runbook_name}")
async def set_runbook_state(
    runbook_name: str,
    req: RunbookToggleRequest,
    principal: dict = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    ok = sre_service.decision_engine.set_runbook_enabled(db, runbook_name=runbook_name, enabled=req.enabled)
    if not ok:
        raise HTTPException(status_code=404, detail="Runbook not found")
    db.add(
        AuditLog(
            actor=str(principal.get("sub", "admin")),
            action=f"runbook_toggle:{runbook_name}",
            resource=f"runbook:{runbook_name}",
            result="success",
            correlation_id=None,
            details={"enabled": req.enabled},
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    return {"status": "updated", "runbook_name": runbook_name, "enabled": req.enabled}

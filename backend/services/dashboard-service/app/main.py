from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI
from sqlalchemy import func
from sqlalchemy.orm import Session

from carop_common.db import Incident, RecoveryQueue, TransactionEvent, get_db, init_db
from carop_common.security import current_principal
from carop_common.web import apply_common_fastapi_config


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="CAROP Dashboard Service", version="1.0.0", lifespan=lifespan)
apply_common_fastapi_config(app)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "dashboard-service"}


@app.get("/api/v1/dashboard/summary")
async def dashboard_summary(_: dict = Depends(current_principal), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    minute_ago = now - timedelta(minutes=1)

    orders_per_minute = (
        db.query(func.count(TransactionEvent.id))
        .filter(TransactionEvent.flow_type == "online_order", TransactionEvent.observed_at >= minute_ago)
        .scalar()
        or 0
    )
    store_billing_per_minute = (
        db.query(func.count(TransactionEvent.id))
        .filter(TransactionEvent.flow_type == "store_billing", TransactionEvent.observed_at >= minute_ago)
        .scalar()
        or 0
    )

    payment_total = (
        db.query(func.count(TransactionEvent.id))
        .filter(TransactionEvent.system_name == "payment_gateway", TransactionEvent.observed_at >= minute_ago)
        .scalar()
        or 0
    )
    payment_success = (
        db.query(func.count(TransactionEvent.id))
        .filter(
            TransactionEvent.system_name == "payment_gateway",
            TransactionEvent.status == "ok",
            TransactionEvent.observed_at >= minute_ago,
        )
        .scalar()
        or 0
    )
    payment_success_rate = (payment_success / payment_total * 100) if payment_total else 100.0

    inventory_latencies = (
        db.query(TransactionEvent)
        .filter(TransactionEvent.flow_type == "inventory", TransactionEvent.observed_at >= minute_ago)
        .all()
    )
    lat_values = [int(x.payload.get("latency_ms", 0)) for x in inventory_latencies if x.payload.get("latency_ms")]
    inventory_sync_latency_ms = int(sum(lat_values) / len(lat_values)) if lat_values else 0

    dispatch_queue_size = (
        db.query(func.count(RecoveryQueue.id)).filter(RecoveryQueue.status == "queued").scalar() or 0
    )

    active = (
        db.query(Incident)
        .filter(Incident.status.in_(["detected", "diagnosed", "auto-fix-running", "pending-replay"]))
        .order_by(Incident.detected_at.desc())
        .limit(20)
        .all()
    )

    return {
        "timestamp": now.isoformat(),
        "global_business_health": {
            "orders_per_minute": orders_per_minute,
            "store_billing_per_minute": store_billing_per_minute,
            "payment_success_rate": round(payment_success_rate, 2),
            "inventory_sync_latency_ms": inventory_sync_latency_ms,
            "dispatch_queue_size": dispatch_queue_size,
        },
        "active_incidents": [
            {
                "id": i.id,
                "root_cause": i.root_cause or "root cause pending",
                "automation": i.metadata_json.get("suggested_runbook", "pending"),
                "status": i.status,
            }
            for i in active
        ],
    }

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from carop_common.db import RecoveryQueue, get_db, init_db
from carop_common.events import KafkaEventPublisher
from carop_common.security import current_principal, require_role
from carop_common.web import apply_common_fastapi_config

publisher = KafkaEventPublisher()


class ReplayRequest(BaseModel):
    flow_type: str
    payload: dict


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    await publisher.start()
    yield
    await publisher.stop()


app = FastAPI(title="CAROP Replay Engine", version="1.0.0", lifespan=lifespan)
apply_common_fastapi_config(app)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "replay-engine"}


@app.post("/api/v1/recovery/queue/{transaction_id}")
async def queue_transaction(
    transaction_id: str,
    req: ReplayRequest,
    _: dict = Depends(current_principal),
    db: Session = Depends(get_db),
):
    dedup_key = sha256(f"{transaction_id}:{req.flow_type}".encode("utf-8")).hexdigest()
    existing = db.query(RecoveryQueue).filter(RecoveryQueue.dedup_key == dedup_key).first()
    if existing:
        return {"status": "already_queued", "item_id": existing.id}

    item = RecoveryQueue(
        transaction_id=transaction_id,
        flow_type=req.flow_type,
        payload=req.payload,
        dedup_key=dedup_key,
        status="queued",
        retry_count=0,
        max_retries=10,
        next_retry_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    await publisher.publish("carop.recovery.queued", {"transaction_id": transaction_id, "item_id": item.id})
    return {"status": "queued", "item_id": item.id}


@app.post("/api/v1/recovery/replay/{transaction_id}")
async def replay_transaction(
    transaction_id: str,
    _: dict = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    item = (
        db.query(RecoveryQueue)
        .filter(RecoveryQueue.transaction_id == transaction_id, RecoveryQueue.status == "queued")
        .order_by(RecoveryQueue.created_at.asc())
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Transaction not found in recovery queue")

    item.status = "replayed"
    item.retry_count += 1
    item.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    item.updated_at = datetime.now(timezone.utc)
    db.commit()

    await publisher.publish("carop.recovery.replayed", {"transaction_id": transaction_id, "item_id": item.id})
    return {"status": "replayed", "transaction_id": transaction_id}


@app.get("/api/v1/recovery/queue")
async def list_queue(_: dict = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.query(RecoveryQueue).order_by(RecoveryQueue.created_at.desc()).limit(200).all()
    return {
        "items": [
            {
                "id": r.id,
                "transaction_id": r.transaction_id,
                "flow_type": r.flow_type,
                "status": r.status,
                "retry_count": r.retry_count,
                "next_retry_at": r.next_retry_at.isoformat(),
            }
            for r in rows
        ]
    }

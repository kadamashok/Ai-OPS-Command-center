import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Any

import httpx
from aiokafka import AIOKafkaConsumer
from fastapi import FastAPI
from jose import jwt

from carop_common.config import settings
from carop_common.web import apply_common_fastapi_config


class EventOrchestrator:
    def __init__(self) -> None:
        self.bootstrap = settings.kafka_bootstrap
        self.group_id = os.getenv("KAFKA_GROUP_ID", "carop-orchestrator-v1")
        self.diagnostic_url = os.getenv("DIAGNOSTIC_URL", "http://diagnostic-engine:8002")
        self.replay_url = os.getenv("REPLAY_URL", "http://replay-engine:8004")

    def _auth_headers(self) -> dict[str, str]:
        token = jwt.encode(
            {"sub": "carop-orchestrator", "roles": ["admin", "operator"]},
            settings.jwt_secret,
            algorithm=settings.jwt_alg,
        )
        return {"Authorization": f"Bearer {token}"}

    async def run(self, stop_event: asyncio.Event) -> None:
        consumer = AIOKafkaConsumer(
            "carop.anomaly.detected",
            bootstrap_servers=self.bootstrap,
            group_id=self.group_id,
            enable_auto_commit=True,
            auto_offset_reset="latest",
        )
        await consumer.start()
        try:
            while not stop_event.is_set():
                batch = await consumer.getmany(timeout_ms=1000, max_records=20)
                for _, messages in batch.items():
                    for msg in messages:
                        payload = json.loads(msg.value.decode("utf-8"))
                        if msg.topic == "carop.anomaly.detected":
                            await self._handle_anomaly(payload)
        finally:
            await consumer.stop()

    async def _handle_anomaly(self, payload: dict[str, Any]) -> None:
        incident_id = payload.get("id")
        if not incident_id:
            return

        headers = self._auth_headers()
        async with httpx.AsyncClient(timeout=20) as client:
            await client.post(f"{self.diagnostic_url}/api/v1/incidents/{incident_id}/diagnose", headers=headers)

            transaction_id = payload.get("transaction_id")
            flow_type = payload.get("flow_type")
            if transaction_id and flow_type:
                await client.post(
                    f"{self.replay_url}/api/v1/recovery/queue/{transaction_id}",
                    json={"flow_type": flow_type, "payload": payload.get("payload", {})},
                    headers=headers,
                )


orchestrator = EventOrchestrator()
stop_event = asyncio.Event()
worker_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global worker_task
    worker_task = asyncio.create_task(orchestrator.run(stop_event))
    yield
    stop_event.set()
    if worker_task:
        await worker_task


app = FastAPI(title="CAROP Orchestrator", version="1.0.0", lifespan=lifespan)
apply_common_fastapi_config(app)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "orchestrator"}

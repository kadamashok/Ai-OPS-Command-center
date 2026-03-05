import importlib.util
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from jose import jwt

# Use isolated sqlite DB for integration tests
os.environ["POSTGRES_DSN"] = "sqlite:///./carop_test.db"
os.environ["JWT_SECRET"] = "test-secret"

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "backend" / "libs" / "common"))


def load_app(rel_path: str):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(path.stem + "_module", str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.app


def auth_headers() -> dict[str, str]:
    token = jwt.encode({"sub": "tester", "roles": ["admin", "operator"]}, "test-secret", algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def test_detect_to_dashboard_to_replay_flow():
    tm_app = load_app("backend/services/transaction-monitor/app/main.py")
    ds_app = load_app("backend/services/dashboard-service/app/main.py")
    re_app = load_app("backend/services/replay-engine/app/main.py")

    headers = auth_headers()
    txn_id = f"TXN-{int(datetime.now(timezone.utc).timestamp())}"

    with TestClient(tm_app) as tm, TestClient(ds_app) as ds, TestClient(re_app) as replay:
        ok_event = {
            "transaction_id": txn_id,
            "flow_type": "online_order",
            "step_name": "payment",
            "system_name": "payment_gateway",
            "status": "ok",
            "payload": {"amount": 12999},
        }
        r1 = tm.post("/api/v1/transactions/events", json=ok_event, headers=headers)
        assert r1.status_code == 200

        fail_event = {
            "transaction_id": txn_id,
            "flow_type": "online_order",
            "step_name": "oms_to_wms",
            "system_name": "wms",
            "status": "failed",
            "payload": {"error": "timeout"},
        }
        r2 = tm.post("/api/v1/transactions/events", json=fail_event, headers=headers)
        assert r2.status_code == 200
        assert r2.json()["status"] == "incident_created"

        rq = replay.post(
            f"/api/v1/recovery/queue/{txn_id}",
            json={"flow_type": "online_order", "payload": {"retry": True}},
            headers=headers,
        )
        assert rq.status_code == 200

        summary = ds.get("/api/v1/dashboard/summary", headers=headers)
        assert summary.status_code == 200
        data = summary.json()
        assert "global_business_health" in data
        assert data["global_business_health"]["orders_per_minute"] >= 1

        rp = replay.post(f"/api/v1/recovery/replay/{txn_id}", headers=headers)
        assert rp.status_code == 200
        assert rp.json()["status"] == "replayed"

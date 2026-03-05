import argparse
import os
import random
import time
from datetime import datetime, timezone

import httpx
from jose import jwt


def build_token(secret: str) -> str:
    payload = {
        "sub": "carop-simulator",
        "roles": ["admin", "operator"],
        "iat": int(time.time()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def send_flow(monitor_url: str, replay_url: str, token: str, tx_id: str, fail_step: str | None) -> None:
    headers = {"Authorization": f"Bearer {token}"}
    steps = [
        ("croma.com", "ok"),
        ("oms", "ok"),
        ("wms", "failed" if fail_step == "wms" else "ok"),
        ("sap", "ok"),
    ]

    with httpx.Client(timeout=10) as client:
        for step, status in steps:
            payload = {
                "transaction_id": tx_id,
                "flow_type": "online_order",
                "step_name": step,
                "system_name": step if step != "croma.com" else "ecommerce",
                "status": status,
                "payload": {"latency_ms": random.randint(30, 350)},
            }
            resp = client.post(f"{monitor_url}/api/v1/transactions/events", json=payload, headers=headers)
            print(step, status, resp.status_code)
            if status == "failed":
                replay_resp = client.post(
                    f"{replay_url}/api/v1/recovery/queue/{tx_id}",
                    json={"flow_type": "online_order", "payload": {"error_step": step}},
                    headers=headers,
                )
                print("queued_recovery", replay_resp.status_code)


def main() -> None:
    parser = argparse.ArgumentParser(description="CAROP synthetic transaction simulator")
    parser.add_argument("--monitor-url", default="http://localhost:8001")
    parser.add_argument("--replay-url", default="http://localhost:8004")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--failure-rate", type=float, default=0.25)
    args = parser.parse_args()

    secret = os.getenv("JWT_SECRET", "change-me-in-prod")
    token = build_token(secret)

    for _ in range(args.count):
        tx_id = f"SIM-{int(datetime.now(timezone.utc).timestamp())}-{random.randint(100,999)}"
        fail = "wms" if random.random() < args.failure_rate else None
        send_flow(args.monitor_url, args.replay_url, token, tx_id, fail)
        time.sleep(0.2)

    print("Simulation complete")


if __name__ == "__main__":
    main()

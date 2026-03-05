from __future__ import annotations

import os
from typing import Any

import httpx
from jose import jwt

from carop_common.config import settings


class VerificationEngine:
    def __init__(self) -> None:
        self.dashboard_url = os.getenv("DASHBOARD_URL", "http://dashboard-service:8006")
        self.transaction_monitor_url = os.getenv("TRANSACTION_MONITOR_URL", "http://transaction-monitor:8001")
        self.incident_url = os.getenv("INCIDENT_URL", "http://incident-service:8007")

    def _headers(self) -> dict[str, str]:
        token = jwt.encode(
            {"sub": "sre-agent", "roles": ["admin", "operator"]},
            settings.jwt_secret,
            algorithm=settings.jwt_alg,
        )
        return {"Authorization": f"Bearer {token}"}

    async def verify(self, incident_id: str, service: str, latency_threshold_ms: int = 1500) -> dict[str, Any]:
        headers = self._headers()
        result: dict[str, Any] = {"verified": False, "checks": []}
        service_upper = service.upper()

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                dash = await client.get(f"{self.dashboard_url}/api/v1/dashboard/summary", headers=headers)
                if dash.status_code == 200:
                    payload = dash.json()
                    latency = int(payload["global_business_health"].get("inventory_sync_latency_ms", 0))
                    ok = latency <= latency_threshold_ms
                    result["checks"].append(
                        {"check": "latency_threshold", "value_ms": latency, "threshold_ms": latency_threshold_ms, "ok": ok}
                    )

                inc = await client.get(f"{self.transaction_monitor_url}/api/v1/incidents", headers=headers)
                if inc.status_code == 200:
                    active = inc.json().get("items", [])
                    service_incidents = [
                        x for x in active if str(x.get("source_system", "")).upper().startswith(service_upper[:3])
                    ]
                    ok = len(service_incidents) <= 1
                    result["checks"].append(
                        {"check": "incident_rate_normalized", "active_for_service": len(service_incidents), "ok": ok}
                    )
        except Exception as exc:  # nosec B110
            result["checks"].append({"check": "verification_exception", "ok": False, "error": str(exc)})

        result["verified"] = all(c.get("ok", False) for c in result["checks"]) if result["checks"] else False
        if result["verified"]:
            await self._close_incident(incident_id=incident_id, headers=headers)
        return result

    async def _close_incident(self, incident_id: str, headers: dict[str, str]) -> None:
        async with httpx.AsyncClient(timeout=20) as client:
            await client.patch(
                f"{self.incident_url}/api/v1/incidents/{incident_id}",
                json={"status": "resolved", "root_cause": "Auto remediated by AI SRE Agent"},
                headers=headers,
            )

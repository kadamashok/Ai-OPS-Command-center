from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx
from jose import jwt
from sqlalchemy.orm import Session

from carop_common.config import settings
from carop_common.db import AuditLog, AutomationAction


class RunbookExecutor:
    def __init__(self) -> None:
        self.automation_url = os.getenv("AUTOMATION_URL", "http://automation-engine:8003")
        self.runbook_executor_url = os.getenv("RUNBOOK_URL", "http://runbook-executor:8005")
        self.service_actor = "AI_SRE_AGENT"
        self._runbook_adapter = {
            "restart_service": "oms_service_crash",
            "scale_kubernetes": "db_pool_exhaustion",
            "retry_api": "wms_api_timeout",
            "clear_queue": "sap_queue_stuck",
        }

    def _headers(self) -> dict[str, str]:
        token = jwt.encode(
            {"sub": "sre-agent", "roles": ["admin", "operator"]},
            settings.jwt_secret,
            algorithm=settings.jwt_alg,
        )
        return {"Authorization": f"Bearer {token}"}

    async def execute(
        self,
        db: Session,
        incident_id: str,
        runbook_name: str,
        trigger: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params = params or {}
        headers = self._headers()

        status = "failed"
        details: dict[str, Any] = {"runbook_name": runbook_name, "trigger": trigger}

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                auto_resp = await client.post(
                    f"{self.automation_url}/api/v1/automation/execute",
                    json={"incident_id": incident_id, "runbook_name": runbook_name, "parameters": params},
                    headers=headers,
                )
                details["automation_engine_status"] = auto_resp.status_code

                mapped = self._runbook_adapter.get(runbook_name)
                if mapped:
                    rb_resp = await client.post(
                        f"{self.runbook_executor_url}/api/v1/runbooks/{mapped}/execute",
                        headers=headers,
                    )
                    details["runbook_executor_status"] = rb_resp.status_code
                    details["runbook_executor_name"] = mapped

                status = "success" if auto_resp.status_code < 300 else "failed"
        except Exception as exc:  # nosec B110
            details["error"] = str(exc)
            status = "failed"

        action = AutomationAction(
            incident_id=incident_id,
            runbook_name=runbook_name,
            trigger=trigger,
            executed_by=self.service_actor,
            status=status,
            details=details,
            executed_at=datetime.now(timezone.utc),
        )
        db.add(action)
        db.add(
            AuditLog(
                actor=self.service_actor,
                action=f"runbook_execute:{runbook_name}",
                resource=f"incident:{incident_id}",
                result=status,
                correlation_id=incident_id,
                details=details,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

        return {"status": status, "details": details}

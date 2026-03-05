from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from redis import Redis
from sqlalchemy.orm import Session

from carop_common.db import IncidentPattern, RunbookCatalog


DEFAULT_PATTERNS = [
    {
        "service": "OMS",
        "error_type": "API_TIMEOUT",
        "pattern_key": "OMS_API_TIMEOUT",
        "severity": "high",
        "probable_root_cause": "OMS API timeout / integration saturation",
        "default_runbook": "restart_service",
    },
    {
        "service": "WMS",
        "error_type": "API_TIMEOUT",
        "pattern_key": "WMS_API_TIMEOUT",
        "severity": "high",
        "probable_root_cause": "WMS API response degradation",
        "default_runbook": "retry_api",
    },
    {
        "service": "SAP",
        "error_type": "QUEUE_STUCK",
        "pattern_key": "SAP_QUEUE_STUCK",
        "severity": "critical",
        "probable_root_cause": "SAP queue backlog / consumer lag",
        "default_runbook": "clear_queue",
    },
    {
        "service": "MPOS",
        "error_type": "SERVICE_UNAVAILABLE",
        "pattern_key": "MPOS_SERVICE_UNAVAILABLE",
        "severity": "high",
        "probable_root_cause": "MPOS sync service unavailable",
        "default_runbook": "restart_service",
    },
]


DEFAULT_RUNBOOKS = [
    {"runbook_name": "restart_service", "description": "Restart affected service workload."},
    {"runbook_name": "scale_kubernetes", "description": "Scale Kubernetes deployment for recovery."},
    {"runbook_name": "retry_api", "description": "Retry failed API calls with backoff."},
    {"runbook_name": "clear_queue", "description": "Drain or clear blocked message queue backlog."},
]


class DecisionEngine:
    def __init__(self) -> None:
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        try:
            self._redis = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=1)
            self._redis.ping()
        except Exception:
            self._redis = None

    def seed_knowledge_base(self, db: Session) -> None:
        for item in DEFAULT_PATTERNS:
            found = db.query(IncidentPattern).filter(IncidentPattern.pattern_key == item["pattern_key"]).first()
            if not found:
                db.add(
                    IncidentPattern(
                        service=item["service"],
                        error_type=item["error_type"],
                        pattern_key=item["pattern_key"],
                        severity=item["severity"],
                        probable_root_cause=item["probable_root_cause"],
                        default_runbook=item["default_runbook"],
                        enabled=True,
                        metadata_json={},
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                )

        for item in DEFAULT_RUNBOOKS:
            found = db.query(RunbookCatalog).filter(RunbookCatalog.runbook_name == item["runbook_name"]).first()
            if not found:
                db.add(
                    RunbookCatalog(
                        runbook_name=item["runbook_name"],
                        description=item["description"],
                        requires_role="operator",
                        enabled=True,
                        verification_policy={"max_latency_ms": 1200},
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
        db.commit()

    def select_runbook(self, db: Session, service: str, error_type: str, pattern_key: str) -> dict[str, Any]:
        cache_key = f"sre:pattern:{pattern_key}"
        if self._redis:
            cached = self._redis.get(cache_key)
            if cached:
                return json.loads(cached)

        pattern = (
            db.query(IncidentPattern)
            .filter(
                IncidentPattern.pattern_key == pattern_key,
                IncidentPattern.enabled.is_(True),
            )
            .first()
        )

        if not pattern:
            pattern = (
                db.query(IncidentPattern)
                .filter(
                    IncidentPattern.service == service,
                    IncidentPattern.error_type == error_type,
                    IncidentPattern.enabled.is_(True),
                )
                .first()
            )

        selected = pattern.default_runbook if pattern else "scale_kubernetes"
        runbook = (
            db.query(RunbookCatalog)
            .filter(RunbookCatalog.runbook_name == selected, RunbookCatalog.enabled.is_(True))
            .first()
        )
        if not runbook:
            selected = "scale_kubernetes"
            runbook = db.query(RunbookCatalog).filter(RunbookCatalog.runbook_name == selected).first()

        result = {
            "runbook_name": selected,
            "requires_role": runbook.requires_role if runbook else "operator",
            "enabled": bool(runbook.enabled) if runbook else True,
        }
        if self._redis:
            self._redis.setex(cache_key, 300, json.dumps(result))
        return result

    def runbook_catalog(self, db: Session) -> list[dict[str, Any]]:
        items = db.query(RunbookCatalog).order_by(RunbookCatalog.runbook_name.asc()).all()
        return [
            {
                "runbook_name": x.runbook_name,
                "description": x.description,
                "requires_role": x.requires_role,
                "enabled": x.enabled,
                "verification_policy": x.verification_policy,
            }
            for x in items
        ]

    def set_runbook_enabled(self, db: Session, runbook_name: str, enabled: bool) -> bool:
        runbook = db.query(RunbookCatalog).filter(RunbookCatalog.runbook_name == runbook_name).first()
        if not runbook:
            return False
        runbook.enabled = enabled
        runbook.updated_at = datetime.now(timezone.utc)
        db.commit()
        if self._redis:
            for pattern in db.query(IncidentPattern).filter(IncidentPattern.default_runbook == runbook_name).all():
                self._redis.delete(f"sre:pattern:{pattern.pattern_key}")
        return True

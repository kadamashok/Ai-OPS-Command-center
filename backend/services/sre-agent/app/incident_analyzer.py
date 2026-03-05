from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class IncidentAnalyzer:
    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        service = str(payload.get("service", "unknown")).upper()
        error_type = str(payload.get("error_type", "UNKNOWN")).upper()
        latency_ms = int(payload.get("latency_ms", 0) or 0)
        root_cause = str(payload.get("root_cause", "")).strip()
        incident_id = str(payload.get("incident_id", ""))

        severity = self._severity_for(error_type=error_type, latency_ms=latency_ms)
        pattern_key = f"{service}_{error_type}"
        probable_root_cause = root_cause or self._root_cause_hint(service, error_type)

        return {
            "incident_id": incident_id,
            "service": service,
            "error_type": error_type,
            "latency_ms": latency_ms,
            "severity": severity,
            "pattern_key": pattern_key,
            "probable_root_cause": probable_root_cause,
            "confidence": self._confidence(error_type=error_type, latency_ms=latency_ms),
            "timestamp": payload.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        }

    def _severity_for(self, error_type: str, latency_ms: int) -> str:
        if error_type in {"AUTH_FAILURE", "DB_DOWN", "QUEUE_STUCK"}:
            return "critical"
        if error_type in {"API_TIMEOUT", "SERVICE_UNAVAILABLE"} or latency_ms >= 5000:
            return "high"
        if latency_ms >= 2000:
            return "medium"
        return "low"

    def _root_cause_hint(self, service: str, error_type: str) -> str:
        hints = {
            "API_TIMEOUT": f"{service} upstream API timeout",
            "QUEUE_STUCK": f"{service} integration queue backlog",
            "SERVICE_UNAVAILABLE": f"{service} service instance unhealthy",
            "AUTH_FAILURE": f"{service} authentication failure spike",
        }
        return hints.get(error_type, f"{service} incident requires further investigation")

    def _confidence(self, error_type: str, latency_ms: int) -> float:
        base = 0.7
        if error_type in {"API_TIMEOUT", "QUEUE_STUCK"}:
            base += 0.2
        if latency_ms >= 5000:
            base += 0.05
        return min(base, 0.99)

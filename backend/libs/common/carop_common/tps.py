from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

try:
    from redis import Redis
except Exception:  # pragma: no cover - optional dependency in local tests
    Redis = None  # type: ignore[assignment]


TRACKED_APPS = [
    "croma.com",
    "OMS",
    "WMS",
    "SAP",
    "Cloud MPOS",
    "Payment gateway APIs",
]

DEFAULT_BASELINE = {
    "croma.com": 20.0,
    "OMS": 15.0,
    "WMS": 12.0,
    "SAP": 10.0,
    "Cloud MPOS": 18.0,
    "Payment gateway APIs": 25.0,
}


def normalize_app(system_name: str) -> str | None:
    s = (system_name or "").strip().lower()
    if s in {"croma.com", "croma", "ecommerce", "web"}:
        return "croma.com"
    if "oms" in s:
        return "OMS"
    if "wms" in s:
        return "WMS"
    if "sap" in s:
        return "SAP"
    if s in {"cloud mpos", "cloud_mpos", "mpos"} or "mpos" in s:
        return "Cloud MPOS"
    if "payment" in s or "pg" in s:
        return "Payment gateway APIs"
    return None


class TpsMetricsStore:
    def __init__(self) -> None:
        self.window_seconds = 300
        self.drop_ratio = float(os.getenv("TPS_DROP_THRESHOLD_RATIO", "0.6"))
        self.spike_ratio = float(os.getenv("TPS_SPIKE_THRESHOLD_RATIO", "1.8"))
        self.baseline = self._load_baseline()
        self._local: dict[str, deque[float]] = defaultdict(deque)

        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        self.redis = None
        if Redis is not None:
            try:
                self.redis = Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=1)
                self.redis.ping()
            except Exception:
                self.redis = None

    def _load_baseline(self) -> dict[str, float]:
        raw = os.getenv("TPS_BASELINE_JSON", "")
        if not raw:
            return dict(DEFAULT_BASELINE)
        try:
            data = json.loads(raw)
            merged = dict(DEFAULT_BASELINE)
            for app in TRACKED_APPS:
                if app in data:
                    merged[app] = float(data[app])
            return merged
        except Exception:
            return dict(DEFAULT_BASELINE)

    def record_event(self, system_name: str, observed_at: datetime | None = None) -> None:
        app = normalize_app(system_name)
        if not app:
            return
        ts = (observed_at or datetime.now(timezone.utc)).timestamp()
        self._record(app, ts)

    def _record(self, app: str, ts: float) -> None:
        if self.redis:
            key = f"carop:tps:{app}"
            self.redis.zadd(key, {f"{ts}-{uuid4()}": ts})
            self.redis.zremrangebyscore(key, 0, ts - self.window_seconds)
            self.redis.expire(key, self.window_seconds + 120)
            return

        q = self._local[app]
        q.append(ts)
        cutoff = ts - self.window_seconds
        while q and q[0] < cutoff:
            q.popleft()

    def snapshot(self) -> dict[str, Any]:
        now = time.time()
        metrics = []
        alerts = []
        for app in TRACKED_APPS:
            count_1s = self._count(app, now - 1, now)
            count_5m = self._count(app, now - self.window_seconds, now)
            current_tps = float(count_1s)
            avg_5m = float(count_5m) / float(self.window_seconds)
            baseline = float(self.baseline.get(app, 1.0))
            status = "normal"
            reason = ""

            if avg_5m < baseline * self.drop_ratio:
                status = "drop"
                reason = "TPS below drop threshold"
            elif avg_5m > baseline * self.spike_ratio or current_tps > baseline * self.spike_ratio:
                status = "spike"
                reason = "TPS above spike threshold"

            row = {
                "application": app,
                "current_tps": round(current_tps, 3),
                "avg_5m_tps": round(avg_5m, 3),
                "baseline_tps": round(baseline, 3),
                "status": status,
            }
            metrics.append(row)
            if status != "normal":
                alerts.append(
                    {
                        "application": app,
                        "status": status,
                        "reason": reason,
                        "current_tps": row["current_tps"],
                        "avg_5m_tps": row["avg_5m_tps"],
                        "baseline_tps": row["baseline_tps"],
                    }
                )

        return {
            "window_seconds": self.window_seconds,
            "thresholds": {"drop_ratio": self.drop_ratio, "spike_ratio": self.spike_ratio},
            "metrics": metrics,
            "alerts": alerts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _count(self, app: str, start_ts: float, end_ts: float) -> int:
        if self.redis:
            key = f"carop:tps:{app}"
            return int(self.redis.zcount(key, start_ts, end_ts))
        q = self._local.get(app, deque())
        return sum(1 for ts in q if start_ts <= ts <= end_ts)


tps_store = TpsMetricsStore()

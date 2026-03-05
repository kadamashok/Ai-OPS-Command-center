from collections import defaultdict
from time import time

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from carop_common.security import current_principal, require_role
from carop_common.web import apply_common_fastapi_config

app = FastAPI(title="CAROP API Gateway", version="1.0.0")
apply_common_fastapi_config(app)

# Simple in-memory rate limiter. Replace with Redis for distributed deployments.
RATE_BUCKETS: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 120
WINDOW_SECONDS = 60


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client = request.client.host if request.client else "unknown"
    now = time()
    bucket = [ts for ts in RATE_BUCKETS[client] if now - ts < WINDOW_SECONDS]
    RATE_BUCKETS[client] = bucket
    if len(bucket) >= RATE_LIMIT:
        return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
    RATE_BUCKETS[client].append(now)
    return await call_next(request)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "api-gateway"}


@app.get("/api/v1/health/global")
async def global_health(_: dict = Depends(current_principal)):
    return {
        "orders_per_minute": 142,
        "store_billing_per_minute": 189,
        "payment_success_rate": 99.2,
        "inventory_sync_latency_ms": 280,
        "dispatch_queue_size": 17,
    }


@app.post("/api/v1/admin/reload-policies")
async def reload_policies(_: dict = Depends(require_role("admin"))):
    return {"status": "accepted", "message": "Policy reload queued"}


@app.exception_handler(HTTPException)
async def handle_http_exception(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

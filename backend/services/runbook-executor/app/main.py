from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import yaml
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from carop_common.db import RunbookExecution, get_db, init_db
from carop_common.security import current_principal, require_role
from carop_common.web import apply_common_fastapi_config

from runbook_engine import RunbookEngine

RUNBOOK_DIR = Path(__file__).resolve().parents[4] / "infra" / "ansible" / "playbooks"
ENGINE = RunbookEngine()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="CAROP Runbook Executor", version="1.0.0", lifespan=lifespan)
apply_common_fastapi_config(app)


def _load_runbook(name: str) -> dict:
    path = RUNBOOK_DIR / f"{name}.yaml"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Runbook not found")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "runbook-executor"}


@app.get("/api/v1/runbooks")
async def list_runbooks(_: dict = Depends(current_principal)):
    items = [p.stem for p in RUNBOOK_DIR.glob("*.yaml")]
    return {"items": sorted(items)}


@app.post("/api/v1/runbooks/{runbook_name}/execute")
async def execute_runbook(
    runbook_name: str,
    _: dict = Depends(require_role("operator")),
    db: Session = Depends(get_db),
):
    runbook = _load_runbook(runbook_name)
    actions = runbook.get("actions", [])
    results = ENGINE.execute_actions(actions)

    for res in results:
        db.add(
            RunbookExecution(
                incident_id="manual",
                runbook_name=runbook_name,
                action_name=res.action,
                executor_type="runbook-engine",
                status=res.status,
                output=res.detail,
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )
        )
    db.commit()

    return {
        "status": "completed",
        "runbook": runbook_name,
        "actions_executed": len(actions),
        "results": [r.__dict__ for r in results],
    }

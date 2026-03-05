from pydantic import BaseModel, Field
from typing import Literal


class TransactionEvent(BaseModel):
    transaction_id: str = Field(min_length=3, max_length=120)
    flow_type: Literal["online_order", "store_billing", "inventory"]
    step_name: str
    system_name: str
    status: Literal["ok", "warning", "failed"]
    payload: dict = Field(default_factory=dict)


class IncidentCreate(BaseModel):
    transaction_id: str | None = None
    source_system: str
    severity: Literal["critical", "high", "medium", "low"]
    title: str
    metadata: dict = Field(default_factory=dict)


class DiagnosticResult(BaseModel):
    incident_id: str
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    checks: list[dict]


class AutomationRequest(BaseModel):
    incident_id: str
    runbook_name: str
    parameters: dict = Field(default_factory=dict)

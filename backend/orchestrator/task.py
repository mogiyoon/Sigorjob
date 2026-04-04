from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


VALID_TASK_STATUSES = {
    "pending",
    "running",
    "done",
    "failed",
    "needs_clarification",
    "approval_required",
    "needs_setup",
    "cancelled",
}


@dataclass
class Step:
    tool: str
    params: dict
    description: str = ""
    risk_level: str = "low"
    result: dict | None = None
    condition: bool | str | None = None
    param_template: bool = False


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    command: str = ""
    intent: str = ""
    steps: list[Step] = field(default_factory=list)
    used_ai: bool = False
    ai_usage: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"   # pending | running | done | failed | needs_clarification | approval_required | needs_setup | cancelled
    approval_reason: str = ""
    risk_level: str = "low"
    results: list[dict] = field(default_factory=list)
    summary: str = ""
    error: str = ""
    result_data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.status not in VALID_TASK_STATUSES:
            raise ValueError(f"invalid task status: {self.status}")

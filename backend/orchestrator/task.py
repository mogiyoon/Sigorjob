from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass
class Step:
    tool: str
    params: dict
    description: str = ""
    risk_level: str = "low"
    result: dict | None = None


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    command: str = ""
    intent: str = ""
    steps: list[Step] = field(default_factory=list)
    status: str = "pending"   # pending | running | done | failed | needs_clarification
    approval_reason: str = ""
    risk_level: str = "low"
    results: list[dict] = field(default_factory=list)
    summary: str = ""
    error: str = ""
    result_data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None

from sqlalchemy import Column, String, Text, DateTime, Enum
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone
import enum


class Base(DeclarativeBase):
    pass


class TaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    needs_clarification = "needs_clarification"
    approval_required = "approval_required"
    needs_setup = "needs_setup"
    cancelled = "cancelled"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ScheduleStatus(str, enum.Enum):
    active = "active"
    paused = "paused"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True)
    command = Column(Text, nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.pending, nullable=False)
    plan = Column(Text, nullable=True)       # AI가 생성한 실행 계획 (JSON)
    result = Column(Text, nullable=True)     # 실행 결과 (JSON)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(String, primary_key=True)
    task_id = Column(String, nullable=False)
    command = Column(Text, nullable=False)
    risk_level = Column(String, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.pending, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    command = Column(Text, nullable=False)
    cron = Column(String, nullable=False)
    status = Column(Enum(ScheduleStatus), default=ScheduleStatus.active, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)


class TaskLog(Base):
    __tablename__ = "task_logs"

    id = Column(String, primary_key=True)
    task_id = Column(String, nullable=False)
    level = Column(String, nullable=False)   # info / warn / error
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class TaskTraceEvent(Base):
    __tablename__ = "task_trace_events"

    id = Column(String, primary_key=True)
    task_id = Column(String, nullable=False)
    stage = Column(String, nullable=False)
    event = Column(String, nullable=False)
    status = Column(String, nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

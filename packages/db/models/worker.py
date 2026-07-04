"""Worker models: registration, heartbeats, and lifecycle events.

Workers register on startup and send periodic heartbeats. If a heartbeat
is missed beyond the configured timeout, the worker is marked as lost
and its claimed jobs are released for other workers to pick up.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base
from packages.shared.types import WorkerStatus


class Worker(Base):
    __tablename__ = "workers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Human-readable hostname + pid identifier, e.g. "worker-7f3a@web-pod-abc"
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[WorkerStatus] = mapped_column(String(20), nullable=False, default=WorkerStatus.ONLINE)
    # Which queues this worker is listening to (comma-separated slugs or "*")
    queue_filter: Mapped[str] = mapped_column(String(500), nullable=False, default="*")
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_workers_project_status", "project_id", "status"),
    )


class WorkerHeartbeat(Base):
    """Rolling heartbeat log. We keep a bounded window (last N) per worker
    for debugging, but the primary liveness check uses worker.last_heartbeat_at
    to avoid scanning this table.
    """

    __tablename__ = "worker_heartbeats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    active_job_count: Mapped[int] = mapped_column(default=0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkerEvent(Base):
    """Lifecycle events: started, stopped, lost, recovered.

    Useful for operational dashboards — "when did this worker go offline?"
    """

    __tablename__ = "worker_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)  # started | stopped | lost | recovered
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

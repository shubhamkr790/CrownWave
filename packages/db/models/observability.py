"""Observability models: job logs and queue metric snapshots.

These tables are append-only and can be partitioned by time or
archived to cold storage in a production deployment.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class JobLog(Base):
    """Structured log entries emitted during job execution.

    Workers write these as the job runs — they show up in the job detail
    view to help operators debug failures without digging through log files.
    """

    __tablename__ = "job_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    level: Mapped[str] = mapped_column(String(10), nullable=False, default="info")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QueueMetricSnapshot(Base):
    """Periodic throughput snapshots per queue.

    The scheduler writes one row per queue every metrics interval (default 60s).
    Dashboard charts read from this table. We don't compute metrics on the
    fly from the jobs table — that would be too expensive at scale.
    """

    __tablename__ = "queue_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    queue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("queues.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Counts at snapshot time
    queued_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    running_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dead_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Throughput in the interval since last snapshot
    jobs_completed_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_failed_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # p50/p95 latency in ms for jobs completed in this interval
    latency_p50_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_p95_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_queue_metrics_lookup", "queue_id", "recorded_at"),
    )

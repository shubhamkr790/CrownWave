"""Job, execution, scheduled job, and dead letter models.

The job table is the hottest table in the system. Indexes are carefully
chosen to support the claim query:

    SELECT id FROM jobs
    WHERE queue_id = :qid AND status = 'queued'
    ORDER BY priority DESC, created_at ASC
    FOR UPDATE SKIP LOCKED
    LIMIT :batch

The composite index (queue_id, status, priority DESC, created_at ASC)
lets Postgres satisfy this without a sort step.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import Base
from packages.shared.types import JobStatus


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Callers can set this to prevent duplicate enqueues
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[JobStatus] = mapped_column(String(20), nullable=False, default=JobStatus.QUEUED)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    queue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("queues.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Which worker currently owns this job (null when queued)
    claimed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workers.id", ondelete="SET NULL"),
        nullable=True,
    )

    attempt_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)

    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Last error message if failed
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Optimistic locking — incremented on every status change
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    executions: Mapped[list["JobExecution"]] = relationship(
        back_populates="job", order_by="JobExecution.attempt_number", lazy="selectin"
    )

    __table_args__ = (
        # The claim query index. Covers queue lookup + status filter + sort order.
        Index("ix_jobs_claim", "queue_id", "status", "priority", "created_at"),
        # Status-only index for dashboard counts
        Index("ix_jobs_status", "status"),
        # Retry scheduler needs to find retry_scheduled jobs by next_retry_at
        Index("ix_jobs_retry_at", "next_retry_at"),
    )


class JobExecution(Base):
    """One row per attempt. A job with max_attempts=3 can have up to 3 executions."""

    __tablename__ = "job_executions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job: Mapped[Job] = relationship(back_populates="executions")

    worker_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workers.id", ondelete="SET NULL"),
        nullable=True,
    )

    attempt_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # completed | failed
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Workers can attach result metadata (e.g., row counts, output refs)
    result_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ScheduledJob(Base):
    """Recurring jobs defined by cron expressions.

    The scheduler process evaluates these on each tick and enqueues new
    Job rows when the next_run_at passes. We track last_run_at to avoid
    double-enqueuing if the scheduler restarts.
    """

    __tablename__ = "scheduled_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    queue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("queues.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_scheduled_jobs_next_run", "next_run_at", "is_active"),
    )


class DeadLetterEntry(Base):
    """Jobs that exhausted all retry attempts end up here.

    We copy relevant fields rather than just referencing the job so the
    DLQ stays useful even if the original job is archived or deleted.
    """

    __tablename__ = "dead_letter_queue"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    job_name: Mapped[str] = mapped_column(String(200), nullable=False)
    queue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # Allows operators to replay or acknowledge entries
    is_resolved: Mapped[bool] = mapped_column(default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    dead_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

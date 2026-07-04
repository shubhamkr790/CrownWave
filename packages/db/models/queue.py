"""Queue and retry policy models.

Queues are the primary unit of work distribution. Each queue has:
- A concurrency limit (how many jobs can run in parallel)
- A priority (workers drain higher-priority queues first)
- An optional default retry policy

Retry policies are reusable across queues. They define how many times
to retry and how to calculate the delay between attempts.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import Base
from packages.shared.types import RetryStrategy


class RetryPolicy(Base):
    __tablename__ = "retry_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    strategy: Mapped[RetryStrategy] = mapped_column(String(20), nullable=False)
    max_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    # Base delay in seconds. Interpretation depends on strategy:
    #   fixed: always wait base_delay_sec
    #   linear: wait base_delay_sec * attempt_number
    #   exponential: wait base_delay_sec * 2^(attempt_number - 1)
    base_delay_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    # Cap so exponential doesn't spiral to hours
    max_delay_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("max_attempts >= 1", name="ck_retry_min_attempts"),
        CheckConstraint("base_delay_sec >= 0", name="ck_retry_nonneg_delay"),
        CheckConstraint("max_delay_sec >= base_delay_sec", name="ck_retry_max_gte_base"),
    )


class Queue(Base):
    __tablename__ = "queues"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Higher number = drained first. Default queues get priority 0.
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    # Max concurrent running jobs for this queue. 0 = unlimited.
    concurrency_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_paused: Mapped[bool] = mapped_column(default=False)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    retry_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("retry_policies.id", ondelete="SET NULL"),
        nullable=True,
    )
    retry_policy: Mapped[RetryPolicy | None] = relationship(lazy="joined")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint("concurrency_limit >= 0", name="ck_queue_concurrency_nonneg"),
    )

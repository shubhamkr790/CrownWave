"""initial schema

Revision ID: 001
Revises: None
Create Date: 2025-01-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- Tenant tables --
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(60), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(254), unique=True, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(60), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_projects_org_slug", "projects", ["organization_id", "slug"], unique=True)

    # -- Queue tables --
    op.create_table(
        "retry_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("strategy", sa.String(20), nullable=False),
        sa.Column("max_attempts", sa.SmallInteger, nullable=False, default=3),
        sa.Column("base_delay_sec", sa.Integer, nullable=False, default=60),
        sa.Column("max_delay_sec", sa.Integer, nullable=False, default=3600),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("max_attempts >= 1", name="ck_retry_min_attempts"),
        sa.CheckConstraint("base_delay_sec >= 0", name="ck_retry_nonneg_delay"),
        sa.CheckConstraint("max_delay_sec >= base_delay_sec", name="ck_retry_max_gte_base"),
    )

    op.create_table(
        "queues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("priority", sa.SmallInteger, nullable=False, default=0),
        sa.Column("concurrency_limit", sa.Integer, nullable=False, default=0),
        sa.Column("is_paused", sa.Boolean, default=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("retry_policy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("retry_policies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("concurrency_limit >= 0", name="ck_queue_concurrency_nonneg"),
    )
    op.create_index("ix_queues_project", "queues", ["project_id"])

    # -- Worker tables (before jobs, since jobs reference workers) --
    op.create_table(
        "workers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="online"),
        sa.Column("queue_filter", sa.String(500), nullable=False, default="*"),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_workers_project_status", "workers", ["project_id", "status"])

    op.create_table(
        "worker_heartbeats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("active_job_count", sa.Integer, default=0),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_worker_heartbeats_worker", "worker_heartbeats", ["worker_id"])

    op.create_table(
        "worker_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_worker_events_worker", "worker_events", ["worker_id"])

    # -- Job tables --
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=True, unique=True),
        sa.Column("payload", postgresql.JSON, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, default="queued"),
        sa.Column("priority", sa.SmallInteger, nullable=False, default=0),
        sa.Column("queue_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("queues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("claimed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("workers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("attempt_count", sa.SmallInteger, nullable=False, default=0),
        sa.Column("max_attempts", sa.SmallInteger, nullable=False, default=3),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, default=1),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    # The claim query index — this is the most performance-critical index
    op.create_index("ix_jobs_claim", "jobs", ["queue_id", "status", "priority", "created_at"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_retry_at", "jobs", ["next_retry_at"])

    # Partial indexes for hot paths — Postgres only
    op.execute("""
        CREATE INDEX ix_jobs_claimable
        ON jobs (queue_id, priority DESC, created_at ASC)
        WHERE status = 'queued'
    """)
    op.execute("""
        CREATE INDEX ix_jobs_retry_pending
        ON jobs (next_retry_at)
        WHERE status = 'retry_scheduled'
    """)

    op.create_table(
        "job_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("worker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("attempt_number", sa.SmallInteger, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("result_meta", postgresql.JSON, nullable=True),
    )
    op.create_index("ix_job_executions_job", "job_executions", ["job_id"])

    op.create_table(
        "scheduled_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("cron_expression", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSON, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("queue_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("queues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_scheduled_jobs_next_run", "scheduled_jobs", ["next_run_at", "is_active"])

    op.create_table(
        "dead_letter_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_name", sa.String(200), nullable=False),
        sa.Column("queue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSON, nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("attempt_count", sa.SmallInteger, nullable=False),
        sa.Column("is_resolved", sa.Boolean, default=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dead_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_dlq_job", "dead_letter_queue", ["job_id"])

    # -- Observability tables --
    op.create_table(
        "job_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", sa.String(10), nullable=False, default="info"),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_job_logs_job", "job_logs", ["job_id"])

    op.create_table(
        "queue_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("queue_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("queues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("queued_count", sa.Integer, nullable=False, default=0),
        sa.Column("running_count", sa.Integer, nullable=False, default=0),
        sa.Column("completed_count", sa.Integer, nullable=False, default=0),
        sa.Column("failed_count", sa.Integer, nullable=False, default=0),
        sa.Column("dead_count", sa.Integer, nullable=False, default=0),
        sa.Column("jobs_completed_interval", sa.Integer, nullable=False, default=0),
        sa.Column("jobs_failed_interval", sa.Integer, nullable=False, default=0),
        sa.Column("latency_p50_ms", sa.Integer, nullable=True),
        sa.Column("latency_p95_ms", sa.Integer, nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_queue_metrics_lookup", "queue_metrics", ["queue_id", "recorded_at"])


def downgrade() -> None:
    op.drop_table("queue_metrics")
    op.drop_table("job_logs")
    op.drop_table("dead_letter_queue")
    op.drop_table("scheduled_jobs")
    op.drop_table("job_executions")
    op.execute("DROP INDEX IF EXISTS ix_jobs_retry_pending")
    op.execute("DROP INDEX IF EXISTS ix_jobs_claimable")
    op.drop_table("jobs")
    op.drop_table("worker_events")
    op.drop_table("worker_heartbeats")
    op.drop_table("workers")
    op.drop_table("queues")
    op.drop_table("retry_policies")
    op.drop_table("projects")
    op.drop_table("users")
    op.drop_table("organizations")

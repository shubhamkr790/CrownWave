# Database seed script for local development.
# Creates a sample org, project, queues, and jobs for testing the dashboard.

import asyncio
import uuid
from datetime import datetime, timezone

from packages.config import get_settings
from packages.db.session import async_session_factory
from packages.db.models.tenant import Organization, Project, User
from packages.db.models.queue import Queue, RetryPolicy
from packages.db.models.job import Job
from packages.logging import configure_logging, get_logger
from apps.api.auth import hash_password
from packages.shared.types import RetryStrategy, JobStatus

log = get_logger(__name__)


async def seed():
    configure_logging()
    log.info("seeding_database")

    async with async_session_factory() as session:
        # Organization
        org = Organization(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            name="Cronwave Dev",
            slug="cronwave-dev",
        )
        session.add(org)
        await session.flush()

        # User
        user = User(
            email="admin@cronwave.dev",
            password_hash=hash_password("admin123"),
            display_name="Admin",
            organization_id=org.id,
        )
        session.add(user)

        # Project
        project = Project(
            id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
            name="Default",
            slug="default",
            organization_id=org.id,
        )
        session.add(project)
        await session.flush()

        # Retry policies
        fixed_policy = RetryPolicy(
            name="Fixed 60s",
            strategy=RetryStrategy.FIXED,
            max_attempts=3,
            base_delay_sec=60,
            max_delay_sec=3600,
            project_id=project.id,
        )
        exp_policy = RetryPolicy(
            name="Exponential backoff",
            strategy=RetryStrategy.EXPONENTIAL,
            max_attempts=5,
            base_delay_sec=30,
            max_delay_sec=1800,
            project_id=project.id,
        )
        session.add_all([fixed_policy, exp_policy])
        await session.flush()

        # Queues
        queues = [
            Queue(name="Email delivery", slug="email", priority=10, concurrency_limit=5, project_id=project.id, retry_policy_id=exp_policy.id),
            Queue(name="Report generation", slug="reports", priority=5, concurrency_limit=2, project_id=project.id, retry_policy_id=fixed_policy.id),
            Queue(name="Data sync", slug="sync", priority=3, concurrency_limit=0, project_id=project.id),
            Queue(name="Webhook dispatch", slug="webhooks", priority=8, concurrency_limit=10, project_id=project.id, retry_policy_id=exp_policy.id),
        ]
        session.add_all(queues)
        await session.flush()

        # Sample jobs across different statuses
        statuses = [
            (JobStatus.QUEUED, 8),
            (JobStatus.RUNNING, 3),
            (JobStatus.COMPLETED, 15),
            (JobStatus.FAILED, 4),
            (JobStatus.RETRY_SCHEDULED, 2),
            (JobStatus.DEAD, 1),
        ]

        job_names = [
            "Send welcome email", "Generate monthly report",
            "Sync user profile", "Dispatch payment webhook",
            "Send password reset", "Export CSV",
            "Rebuild search index", "Process refund notification",
            "Sync inventory", "Send invoice",
        ]

        job_count = 0
        for status, count in statuses:
            for i in range(count):
                job = Job(
                    name=job_names[job_count % len(job_names)],
                    queue_id=queues[job_count % len(queues)].id,
                    status=status,
                    priority=job_count % 3,
                    payload={"user_id": str(uuid.uuid4())[:8], "type": "seed"},
                    attempt_count=1 if status != JobStatus.QUEUED else 0,
                    max_attempts=3,
                )
                if status == JobStatus.FAILED:
                    job.last_error = "Connection timeout after 30s"
                if status == JobStatus.DEAD:
                    job.last_error = "Service unavailable (5 attempts exhausted)"
                    job.attempt_count = 5
                session.add(job)
                job_count += 1

        await session.commit()
        log.info("seed_complete", jobs=job_count, queues=len(queues))


if __name__ == "__main__":
    asyncio.run(seed())

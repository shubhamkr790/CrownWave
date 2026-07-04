"""Job repository — the most complex repo in the system.

Handles atomic claiming, retry scheduling, and dead letter routing.
Every method that modifies job state does so within a transaction.
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select, update, text
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.job import DeadLetterEntry, Job, JobExecution
from packages.db.models.queue import Queue
from packages.logging import get_logger
from packages.shared.types import JobStatus

log = get_logger(__name__)


class JobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, job: Job) -> Job:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(self, job_id: uuid.UUID) -> Job | None:
        return await self.session.get(Job, job_id)

    async def list_jobs(
        self,
        *,
        queue_id: uuid.UUID | None = None,
        status: JobStatus | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> tuple[list[Job], int]:
        """Paginated job listing with optional filters."""
        query = select(Job)
        count_query = select(func.count(Job.id))

        if queue_id:
            query = query.where(Job.queue_id == queue_id)
            count_query = count_query.where(Job.queue_id == queue_id)
        if status:
            query = query.where(Job.status == status)
            count_query = count_query.where(Job.status == status)

        query = query.order_by(Job.created_at.desc())
        query = query.offset((page - 1) * per_page).limit(per_page)

        result = await self.session.execute(query)
        total = await self.session.scalar(count_query)
        return list(result.scalars().all()), total or 0

    async def claim_next_jobs(
        self,
        queue_id: uuid.UUID,
        worker_id: uuid.UUID,
        batch_size: int = 1,
    ) -> list[Job]:
        """Atomically claim the next N queued jobs from a queue.

        Uses FOR UPDATE SKIP LOCKED to avoid blocking other workers.
        This is the standard approach at companies like Stripe and Uber
        for queue-based job systems backed by Postgres.

        Why SKIP LOCKED instead of NOWAIT:
        - NOWAIT raises an error if the row is locked, forcing retry logic.
        - SKIP LOCKED silently skips locked rows and returns available ones.
        - For a multi-worker job queue, SKIP LOCKED gives better throughput
          because workers don't contend — they each grab different rows.
        """
        now = datetime.now(timezone.utc)

        # Step 1: Find claimable job IDs with row-level locking
        subquery = (
            select(Job.id)
            .where(
                and_(
                    Job.queue_id == queue_id,
                    Job.status == JobStatus.QUEUED,
                )
            )
            .order_by(Job.priority.desc(), Job.created_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(subquery)
        job_ids = [row[0] for row in result.all()]

        if not job_ids:
            return []

        # Step 2: Update those jobs atomically
        stmt = (
            update(Job)
            .where(Job.id.in_(job_ids))
            .values(
                status=JobStatus.CLAIMED,
                claimed_by=worker_id,
                claimed_at=now,
                version=Job.version + 1,
            )
            .returning(Job)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()

        claimed = list(result.scalars().all())
        log.info(
            "jobs_claimed",
            count=len(claimed),
            queue_id=str(queue_id),
            worker_id=str(worker_id),
        )
        return claimed

    async def mark_running(self, job_id: uuid.UUID) -> None:
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=JobStatus.RUNNING,
                started_at=now,
                attempt_count=Job.attempt_count + 1,
                version=Job.version + 1,
            )
        )
        await self.session.flush()

    async def mark_completed(self, job_id: uuid.UUID) -> None:
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(
                status=JobStatus.COMPLETED,
                completed_at=now,
                claimed_by=None,
                version=Job.version + 1,
            )
        )
        await self.session.flush()

    async def mark_failed(
        self,
        job_id: uuid.UUID,
        error: str,
        retry_delay_sec: int | None = None,
    ) -> None:
        """Mark a job as failed. If retry_delay_sec is provided and attempts
        remain, schedule a retry. Otherwise, move to dead letter queue.
        """
        job = await self.get_by_id(job_id)
        if not job:
            return

        now = datetime.now(timezone.utc)

        if retry_delay_sec is not None and job.attempt_count < job.max_attempts:
            # Schedule retry
            next_retry = now + timedelta(seconds=retry_delay_sec)
            await self.session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status=JobStatus.RETRY_SCHEDULED,
                    last_error=error,
                    next_retry_at=next_retry,
                    claimed_by=None,
                    version=Job.version + 1,
                )
            )
            log.info("job_retry_scheduled", job_id=str(job_id), next_retry_at=next_retry.isoformat())
        else:
            # Exhausted retries — move to DLQ
            await self._send_to_dlq(job, error)
            await self.session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(
                    status=JobStatus.DEAD,
                    last_error=error,
                    claimed_by=None,
                    version=Job.version + 1,
                )
            )
            log.warning("job_dead_lettered", job_id=str(job_id), attempts=job.attempt_count)

        await self.session.flush()

    async def requeue_retryable_jobs(self) -> int:
        """Move retry_scheduled jobs back to queued when their retry time arrives.

        Called periodically by the scheduler process.
        """
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            update(Job)
            .where(
                and_(
                    Job.status == JobStatus.RETRY_SCHEDULED,
                    Job.next_retry_at <= now,
                )
            )
            .values(
                status=JobStatus.QUEUED,
                next_retry_at=None,
                version=Job.version + 1,
            )
        )
        count = result.rowcount
        if count:
            log.info("retryable_jobs_requeued", count=count)
        return count

    async def recover_stale_claims(self, timeout_sec: float) -> int:
        """Release jobs stuck in claimed/running state from dead workers.

        This happens when a worker crashes without completing its jobs.
        We look for jobs that were claimed more than timeout_sec ago and
        haven't been updated. They get re-queued so another worker can
        pick them up.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_sec)
        result = await self.session.execute(
            update(Job)
            .where(
                and_(
                    Job.status.in_([JobStatus.CLAIMED, JobStatus.RUNNING]),
                    Job.claimed_at < cutoff,
                )
            )
            .values(
                status=JobStatus.QUEUED,
                claimed_by=None,
                claimed_at=None,
                version=Job.version + 1,
            )
        )
        count = result.rowcount
        if count:
            log.warning("stale_claims_recovered", count=count, cutoff=cutoff.isoformat())
        return count

    async def record_execution(self, execution: JobExecution) -> None:
        self.session.add(execution)
        await self.session.flush()

    async def cancel(self, job_id: uuid.UUID) -> bool:
        """Cancel a job if it's in a cancellable state."""
        result = await self.session.execute(
            update(Job)
            .where(
                and_(
                    Job.id == job_id,
                    Job.status.in_([JobStatus.QUEUED, JobStatus.SCHEDULED, JobStatus.RETRY_SCHEDULED]),
                )
            )
            .values(
                status=JobStatus.CANCELLED,
                version=Job.version + 1,
            )
        )
        return result.rowcount > 0

    async def count_by_status(self, queue_id: uuid.UUID | None = None) -> dict[str, int]:
        """Status counts for a queue (or all queues). Used by the dashboard."""
        query = select(Job.status, func.count(Job.id)).group_by(Job.status)
        if queue_id:
            query = query.where(Job.queue_id == queue_id)
        result = await self.session.execute(query)
        return {row[0]: row[1] for row in result.all()}

    async def _send_to_dlq(self, job: Job, error: str) -> None:
        entry = DeadLetterEntry(
            job_id=job.id,
            job_name=job.name,
            queue_id=job.queue_id,
            payload=job.payload,
            last_error=error,
            attempt_count=job.attempt_count,
        )
        self.session.add(entry)

"""Scheduler process: manages cron-based recurring jobs and retry requeuing.

Runs on a configurable tick interval. Each tick:
1. Checks for scheduled jobs whose next_run_at has passed
2. Enqueues new Job rows for those scheduled jobs
3. Re-queues retry_scheduled jobs whose delay has elapsed
4. Records metric snapshots for dashboard charts

Only one scheduler instance should run at a time. In a multi-node
deployment, you'd use a Redis-based leader election or a Postgres
advisory lock. For now, it's a single process.
"""
import asyncio
import signal
from datetime import datetime, timezone

from croniter import croniter
from sqlalchemy import and_, select, update, func

from packages.config import get_settings
from packages.db.session import async_session_factory
from packages.db.models.job import Job, ScheduledJob
from packages.db.models.queue import Queue
from packages.db.models.observability import QueueMetricSnapshot
from packages.db.repositories.job_repo import JobRepository
from packages.logging import configure_logging, get_logger
from packages.shared.types import JobStatus

log = get_logger(__name__)


class SchedulerProcess:
    def __init__(self):
        self.settings = get_settings()
        self._shutdown = asyncio.Event()

    async def start(self):
        configure_logging()
        log.info("scheduler_starting", tick_interval=self.settings.scheduler_tick_interval_sec)
        self._register_signals()

        while not self._shutdown.is_set():
            try:
                await self._tick()
            except Exception:
                log.exception("scheduler_tick_error")

            try:
                await asyncio.wait_for(
                    self._shutdown.wait(),
                    timeout=self.settings.scheduler_tick_interval_sec,
                )
                break
            except asyncio.TimeoutError:
                continue

        log.info("scheduler_stopped")

    async def _tick(self):
        await self._enqueue_scheduled_jobs()
        await self._requeue_retryable_jobs()
        await self._record_metrics()

    async def _enqueue_scheduled_jobs(self):
        """Check for cron jobs that need to fire."""
        now = datetime.now(timezone.utc)

        async with async_session_factory() as session:
            result = await session.execute(
                select(ScheduledJob).where(
                    and_(
                        ScheduledJob.is_active == True,
                        ScheduledJob.next_run_at <= now,
                    )
                )
            )
            due_jobs = result.scalars().all()

            for scheduled in due_jobs:
                # Enqueue a new job instance
                job = Job(
                    name=f"{scheduled.name} (scheduled)",
                    queue_id=scheduled.queue_id,
                    payload=scheduled.payload,
                )
                session.add(job)

                # Advance next_run_at
                next_run = croniter(scheduled.cron_expression, now).get_next(datetime)
                scheduled.last_run_at = now
                scheduled.next_run_at = next_run

                log.info(
                    "scheduled_job_enqueued",
                    name=scheduled.name,
                    next_run=next_run.isoformat(),
                )

            await session.commit()

    async def _requeue_retryable_jobs(self):
        async with async_session_factory() as session:
            repo = JobRepository(session)
            count = await repo.requeue_retryable_jobs()
            await session.commit()

    async def _record_metrics(self):
        """Snapshot job counts per queue for the dashboard charts."""
        async with async_session_factory() as session:
            result = await session.execute(select(Queue))
            queues = result.scalars().all()

            for queue in queues:
                counts = {}
                count_result = await session.execute(
                    select(Job.status, func.count(Job.id))
                    .where(Job.queue_id == queue.id)
                    .group_by(Job.status)
                )
                for status, count in count_result.all():
                    key = status.value if hasattr(status, "value") else status
                    counts[key] = count

                snapshot = QueueMetricSnapshot(
                    queue_id=queue.id,
                    queued_count=counts.get("queued", 0),
                    running_count=counts.get("running", 0),
                    completed_count=counts.get("completed", 0),
                    failed_count=counts.get("failed", 0),
                    dead_count=counts.get("dead", 0),
                )
                session.add(snapshot)

            await session.commit()

    def _register_signals(self):
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, lambda: self._shutdown.set())
            except NotImplementedError:
                signal.signal(sig, lambda s, f: self._shutdown.set())

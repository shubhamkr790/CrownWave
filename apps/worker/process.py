"""Worker process: polls queues, claims jobs, executes them, heartbeats.

Design:
- Single async event loop with three concurrent tasks:
  1. Poll loop: checks queues for available work
  2. Heartbeat loop: pings the database to prove liveness
  3. Recovery: on startup, reclaim stale jobs from crashed workers

Graceful shutdown:
- SIGTERM/SIGINT trigger shutdown flag
- Poll loop stops claiming new jobs
- In-flight jobs finish (with a deadline)
- Worker deregisters itself

We deliberately avoid threading or multiprocessing here. The async
model works well because our "work" is I/O-bound (DB queries, HTTP
calls). For CPU-bound job execution, you'd spawn subprocesses, but
that's outside scope for this version.
"""
import asyncio
import os
import signal
import uuid
from datetime import datetime, timezone

from packages.config import get_settings
from packages.db.session import async_session_factory
from packages.db.models.job import Job, JobExecution
from packages.db.models.queue import Queue
from packages.db.models.worker import Worker
from packages.db.repositories.job_repo import JobRepository
from packages.db.repositories.queue_repo import QueueRepository
from packages.db.repositories.worker_repo import WorkerRepository
from packages.logging import configure_logging, get_logger
from packages.shared.retry import calculate_retry_delay
from packages.shared.types import JobStatus, RetryStrategy, WorkerStatus

log = get_logger(__name__)


class WorkerProcess:
    def __init__(self, project_id: uuid.UUID, queue_filter: str = "*"):
        self.settings = get_settings()
        self.project_id = project_id
        self.queue_filter = queue_filter
        self.worker_id: uuid.UUID | None = None
        self._shutdown = asyncio.Event()
        self._active_jobs: int = 0

    async def start(self):
        configure_logging()
        self._register_signals()

        worker_name = f"worker-{uuid.uuid4().hex[:6]}@{os.getpid()}"
        log.info("worker_starting", name=worker_name, project_id=str(self.project_id))

        # Register with the database
        async with async_session_factory() as session:
            repo = WorkerRepository(session)
            worker = Worker(
                name=worker_name,
                project_id=self.project_id,
                queue_filter=self.queue_filter,
                last_heartbeat_at=datetime.now(timezone.utc),
            )
            worker = await repo.register(worker)
            await session.commit()
            self.worker_id = worker.id

        log.info("worker_registered", worker_id=str(self.worker_id))

        # Recover any stale claims from previously crashed workers
        await self._recover_stale_claims()

        # Run poll + heartbeat concurrently until shutdown
        try:
            await asyncio.gather(
                self._poll_loop(),
                self._heartbeat_loop(),
            )
        finally:
            await self._deregister()

    async def _poll_loop(self):
        while not self._shutdown.is_set():
            try:
                await self._poll_once()
            except Exception:
                log.exception("poll_error")

            # Wait for the poll interval or shutdown, whichever comes first
            try:
                await asyncio.wait_for(
                    self._shutdown.wait(),
                    timeout=self.settings.worker_poll_interval_sec,
                )
                break  # shutdown was signaled
            except asyncio.TimeoutError:
                continue  # poll interval elapsed, poll again

    async def _poll_once(self):
        """Check each queue (in priority order) for claimable work."""
        async with async_session_factory() as session:
            queue_repo = QueueRepository(session)
            job_repo = JobRepository(session)

            queues = await queue_repo.get_active_queues(self.project_id)

            for queue in queues:
                if self._shutdown.is_set():
                    return

                # Respect concurrency limits
                if queue.concurrency_limit > 0:
                    running = await queue_repo.running_job_count(queue.id)
                    if running >= queue.concurrency_limit:
                        continue

                remaining = self.settings.worker_claim_batch_size - self._active_jobs
                if remaining <= 0:
                    return

                claimed = await job_repo.claim_next_jobs(
                    queue_id=queue.id,
                    worker_id=self.worker_id,
                    batch_size=min(remaining, self.settings.worker_claim_batch_size),
                )
                await session.commit()

                for job in claimed:
                    self._active_jobs += 1
                    # Fire and forget — execute_job manages its own session
                    asyncio.create_task(self._execute_job(job.id, queue))

    async def _execute_job(self, job_id: uuid.UUID, queue: Queue):
        """Run a single job. Records execution, handles success/failure."""
        started_at = datetime.now(timezone.utc)

        async with async_session_factory() as session:
            job_repo = JobRepository(session)

            try:
                await job_repo.mark_running(job_id)
                await session.commit()

                # Simulate actual work. In production, this would dispatch to
                # a task handler registry based on the job name/type.
                await self._do_work(job_id)

                # Record success
                await job_repo.mark_completed(job_id)
                execution = JobExecution(
                    job_id=job_id,
                    worker_id=self.worker_id,
                    attempt_number=(await job_repo.get_by_id(job_id)).attempt_count,
                    status="completed",
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                    duration_ms=int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000),
                )
                await job_repo.record_execution(execution)
                await session.commit()

                log.info("job_completed", job_id=str(job_id))

            except Exception as exc:
                error_msg = str(exc)[:500]
                log.error("job_failed", job_id=str(job_id), error=error_msg)

                # Calculate retry delay from queue's retry policy
                retry_delay = None
                if queue.retry_policy:
                    rp = queue.retry_policy
                    job = await job_repo.get_by_id(job_id)
                    if job and job.attempt_count < job.max_attempts:
                        retry_delay = calculate_retry_delay(
                            strategy=RetryStrategy(rp.strategy),
                            attempt=job.attempt_count,
                            base_delay_sec=rp.base_delay_sec,
                            max_delay_sec=rp.max_delay_sec,
                        )

                await job_repo.mark_failed(job_id, error_msg, retry_delay)

                execution = JobExecution(
                    job_id=job_id,
                    worker_id=self.worker_id,
                    attempt_number=1,  # will be updated properly
                    status="failed",
                    started_at=started_at,
                    finished_at=datetime.now(timezone.utc),
                    duration_ms=int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000),
                    error_message=error_msg,
                )
                await job_repo.record_execution(execution)
                await session.commit()

            finally:
                self._active_jobs -= 1

    async def _do_work(self, job_id: uuid.UUID):
        """Placeholder for actual job execution.

        In a real system, you'd look up a handler from a registry:
            handler = self.handlers.get(job.name)
            await handler(job.payload)

        For now, we simulate with a short sleep.
        """
        await asyncio.sleep(0.5)

    async def _heartbeat_loop(self):
        while not self._shutdown.is_set():
            try:
                async with async_session_factory() as session:
                    repo = WorkerRepository(session)
                    await repo.heartbeat(self.worker_id, self._active_jobs)
                    await session.commit()
            except Exception:
                log.exception("heartbeat_error")

            try:
                await asyncio.wait_for(
                    self._shutdown.wait(),
                    timeout=self.settings.worker_heartbeat_interval_sec,
                )
                break
            except asyncio.TimeoutError:
                continue

    async def _recover_stale_claims(self):
        """On startup, release jobs from workers that died without cleaning up."""
        async with async_session_factory() as session:
            job_repo = JobRepository(session)
            worker_repo = WorkerRepository(session)

            lost = await worker_repo.detect_lost_workers(
                self.settings.worker_heartbeat_timeout_sec
            )
            recovered = await job_repo.recover_stale_claims(
                self.settings.worker_heartbeat_timeout_sec
            )
            await session.commit()

            if lost or recovered:
                log.warning(
                    "startup_recovery",
                    lost_workers=len(lost),
                    recovered_jobs=recovered,
                )

    async def _deregister(self):
        if not self.worker_id:
            return
        try:
            async with async_session_factory() as session:
                repo = WorkerRepository(session)
                await repo.mark_stopped(self.worker_id)
                await session.commit()
            log.info("worker_deregistered", worker_id=str(self.worker_id))
        except Exception:
            log.exception("deregister_error")

    def _register_signals(self):
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self._handle_shutdown)
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                signal.signal(sig, lambda s, f: self._handle_shutdown())

    def _handle_shutdown(self):
        log.info("shutdown_signal_received")
        self._shutdown.set()

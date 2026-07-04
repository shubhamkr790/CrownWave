"""Worker repository — registration, heartbeating, and zombie detection."""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.worker import Worker, WorkerEvent, WorkerHeartbeat
from packages.logging import get_logger
from packages.shared.types import WorkerStatus

log = get_logger(__name__)


class WorkerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def register(self, worker: Worker) -> Worker:
        self.session.add(worker)
        await self.session.flush()
        event = WorkerEvent(
            worker_id=worker.id,
            event_type="started",
            detail=f"Worker {worker.name} registered",
        )
        self.session.add(event)
        await self.session.flush()
        log.info("worker_registered", worker_id=str(worker.id), name=worker.name)
        return worker

    async def heartbeat(self, worker_id: uuid.UUID, active_jobs: int = 0) -> None:
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(Worker)
            .where(Worker.id == worker_id)
            .values(last_heartbeat_at=now)
        )
        beat = WorkerHeartbeat(
            worker_id=worker_id,
            active_job_count=active_jobs,
        )
        self.session.add(beat)
        await self.session.flush()

    async def mark_stopped(self, worker_id: uuid.UUID) -> None:
        now = datetime.now(timezone.utc)
        await self.session.execute(
            update(Worker)
            .where(Worker.id == worker_id)
            .values(status=WorkerStatus.OFFLINE, stopped_at=now)
        )
        event = WorkerEvent(
            worker_id=worker_id,
            event_type="stopped",
            detail="Graceful shutdown",
        )
        self.session.add(event)
        await self.session.flush()
        log.info("worker_stopped", worker_id=str(worker_id))

    async def detect_lost_workers(self, timeout_sec: float) -> list[Worker]:
        """Find workers that haven't sent a heartbeat within the timeout.

        These are likely crashed. We mark them as lost and emit an event
        so the stale claim recovery can release their jobs.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout_sec)
        result = await self.session.execute(
            select(Worker).where(
                and_(
                    Worker.status == WorkerStatus.ONLINE,
                    Worker.last_heartbeat_at < cutoff,
                )
            )
        )
        lost = list(result.scalars().all())

        if lost:
            worker_ids = [w.id for w in lost]
            await self.session.execute(
                update(Worker)
                .where(Worker.id.in_(worker_ids))
                .values(status=WorkerStatus.LOST)
            )
            for w in lost:
                event = WorkerEvent(
                    worker_id=w.id,
                    event_type="lost",
                    detail=f"No heartbeat since {w.last_heartbeat_at}",
                )
                self.session.add(event)

            await self.session.flush()
            log.warning("lost_workers_detected", count=len(lost))

        return lost

    async def list_by_project(self, project_id: uuid.UUID) -> list[Worker]:
        result = await self.session.execute(
            select(Worker)
            .where(Worker.project_id == project_id)
            .order_by(Worker.started_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, worker_id: uuid.UUID) -> Worker | None:
        return await self.session.get(Worker, worker_id)

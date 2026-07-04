"""Queue repository — CRUD plus concurrency-aware queries."""
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.job import Job
from packages.db.models.queue import Queue
from packages.shared.types import JobStatus


class QueueRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, queue: Queue) -> Queue:
        self.session.add(queue)
        await self.session.flush()
        return queue

    async def get_by_id(self, queue_id: uuid.UUID) -> Queue | None:
        return await self.session.get(Queue, queue_id)

    async def list_by_project(self, project_id: uuid.UUID) -> list[Queue]:
        result = await self.session.execute(
            select(Queue)
            .where(Queue.project_id == project_id)
            .order_by(Queue.priority.desc(), Queue.name.asc())
        )
        return list(result.scalars().all())

    async def get_active_queues(self, project_id: uuid.UUID) -> list[Queue]:
        """Non-paused queues, ordered by priority for worker polling."""
        result = await self.session.execute(
            select(Queue)
            .where(Queue.project_id == project_id, Queue.is_paused == False)
            .order_by(Queue.priority.desc())
        )
        return list(result.scalars().all())

    async def running_job_count(self, queue_id: uuid.UUID) -> int:
        """How many jobs are currently running in this queue.
        Workers check this against concurrency_limit before claiming.
        """
        result = await self.session.scalar(
            select(func.count(Job.id))
            .where(Job.queue_id == queue_id, Job.status == JobStatus.RUNNING)
        )
        return result or 0

    async def update_pause_state(self, queue_id: uuid.UUID, paused: bool) -> bool:
        result = await self.session.execute(
            update(Queue).where(Queue.id == queue_id).values(is_paused=paused)
        )
        return result.rowcount > 0

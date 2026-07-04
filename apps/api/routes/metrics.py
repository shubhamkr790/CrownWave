from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import AuthContext, get_current_user
from packages.db import get_session
from packages.db.models.job import Job, DeadLetterEntry
from packages.db.models.queue import Queue
from packages.db.models.worker import Worker
from packages.db.models.tenant import Project
from packages.db.models.observability import QueueMetricSnapshot
from packages.shared.envelope import ApiResponse
from packages.shared.types import JobStatus, WorkerStatus

router = APIRouter()


@router.get("/overview")
async def metrics_overview(
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Dashboard overview: job counts, worker counts, queue health."""
    project = await session.scalar(
        select(Project).where(Project.organization_id == auth.org_id).limit(1)
    )
    if not project:
        return ApiResponse.ok(_empty_overview())

    # Job status distribution
    job_counts = {}
    result = await session.execute(
        select(Job.status, func.count(Job.id))
        .join(Queue, Job.queue_id == Queue.id)
        .where(Queue.project_id == project.id)
        .group_by(Job.status)
    )
    for status, count in result.all():
        key = status.value if hasattr(status, "value") else status
        job_counts[key] = count

    # Worker status distribution
    worker_counts = {}
    result = await session.execute(
        select(Worker.status, func.count(Worker.id))
        .where(Worker.project_id == project.id)
        .group_by(Worker.status)
    )
    for status, count in result.all():
        key = status.value if hasattr(status, "value") else status
        worker_counts[key] = count

    # Queue count
    queue_count = await session.scalar(
        select(func.count(Queue.id)).where(Queue.project_id == project.id)
    ) or 0

    # DLQ count
    dlq_count = await session.scalar(
        select(func.count(DeadLetterEntry.id))
        .where(DeadLetterEntry.is_resolved == False)
    ) or 0

    total_jobs = sum(job_counts.values())
    completed = job_counts.get("completed", 0)
    failed = job_counts.get("failed", 0) + job_counts.get("dead", 0)
    success_rate = round((completed / total_jobs * 100), 1) if total_jobs > 0 else 0

    return ApiResponse.ok({
        "jobs": {
            "total": total_jobs,
            "by_status": job_counts,
            "success_rate": success_rate,
        },
        "workers": {
            "total": sum(worker_counts.values()),
            "by_status": worker_counts,
        },
        "queues": {
            "total": queue_count,
        },
        "dlq": {
            "unresolved": dlq_count,
        },
    })


def _empty_overview():
    return {
        "jobs": {"total": 0, "by_status": {}, "success_rate": 0},
        "workers": {"total": 0, "by_status": {}},
        "queues": {"total": 0},
        "dlq": {"unresolved": 0},
    }

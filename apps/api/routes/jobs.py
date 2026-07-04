import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import AuthContext, get_current_user
from packages.db import get_session
from packages.db.models.job import Job
from packages.db.repositories.job_repo import JobRepository
from packages.shared.envelope import ApiResponse, PaginationMeta
from packages.shared.errors import NotFoundError
from packages.shared.types import JobStatus

router = APIRouter()


class EnqueueJobRequest(BaseModel):
    name: str
    queue_id: uuid.UUID
    payload: dict | None = None
    priority: int = 0
    max_attempts: int = 3
    idempotency_key: str | None = None


class JobResponse(BaseModel):
    id: str
    name: str
    status: str
    priority: int
    queue_id: str
    attempt_count: int
    max_attempts: int
    idempotency_key: str | None
    last_error: str | None
    created_at: str
    claimed_at: str | None
    started_at: str | None
    completed_at: str | None

    @classmethod
    def from_model(cls, job: Job) -> "JobResponse":
        return cls(
            id=str(job.id),
            name=job.name,
            status=job.status.value if isinstance(job.status, JobStatus) else job.status,
            priority=job.priority,
            queue_id=str(job.queue_id),
            attempt_count=job.attempt_count,
            max_attempts=job.max_attempts,
            idempotency_key=job.idempotency_key,
            last_error=job.last_error,
            created_at=job.created_at.isoformat() if job.created_at else "",
            claimed_at=job.claimed_at.isoformat() if job.claimed_at else None,
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
        )


@router.post("")
async def enqueue_job(
    body: EnqueueJobRequest,
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = JobRepository(session)
    job = Job(
        name=body.name,
        queue_id=body.queue_id,
        payload=body.payload,
        priority=body.priority,
        max_attempts=body.max_attempts,
        idempotency_key=body.idempotency_key,
    )
    job = await repo.create(job)
    return ApiResponse.ok(JobResponse.from_model(job).model_dump())


@router.get("")
async def list_jobs(
    queue_id: uuid.UUID | None = None,
    status: JobStatus | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = JobRepository(session)
    jobs, total = await repo.list_jobs(
        queue_id=queue_id, status=status, page=page, per_page=per_page
    )
    total_pages = (total + per_page - 1) // per_page

    return ApiResponse.ok(
        data=[JobResponse.from_model(j).model_dump() for j in jobs],
        pagination=PaginationMeta(
            page=page, per_page=per_page, total=total, total_pages=total_pages
        ),
    )


@router.get("/{job_id}")
async def get_job(
    job_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = JobRepository(session)
    job = await repo.get_by_id(job_id)
    if not job:
        raise NotFoundError("Job", str(job_id))

    data = JobResponse.from_model(job).model_dump()
    # Include execution history in detail view
    data["executions"] = [
        {
            "id": str(e.id),
            "attempt_number": e.attempt_number,
            "status": e.status,
            "started_at": e.started_at.isoformat(),
            "finished_at": e.finished_at.isoformat() if e.finished_at else None,
            "duration_ms": e.duration_ms,
            "error_message": e.error_message,
        }
        for e in job.executions
    ]
    return ApiResponse.ok(data)


@router.post("/{job_id}/retry")
async def retry_job(
    job_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Manually re-queue a failed or dead job."""
    repo = JobRepository(session)
    job = await repo.get_by_id(job_id)
    if not job:
        raise NotFoundError("Job", str(job_id))

    from sqlalchemy import update
    from packages.db.models.job import Job as JobModel

    await session.execute(
        update(JobModel)
        .where(JobModel.id == job_id)
        .values(
            status=JobStatus.QUEUED,
            claimed_by=None,
            claimed_at=None,
            last_error=None,
            next_retry_at=None,
            version=JobModel.version + 1,
        )
    )
    await session.flush()

    updated = await repo.get_by_id(job_id)
    return ApiResponse.ok(JobResponse.from_model(updated).model_dump())


@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = JobRepository(session)
    cancelled = await repo.cancel(job_id)
    if not cancelled:
        raise NotFoundError("Job", str(job_id))
    return ApiResponse.ok({"id": str(job_id), "status": "cancelled"})

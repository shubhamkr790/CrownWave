import uuid
from datetime import datetime, timezone

from croniter import croniter
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import AuthContext, get_current_user
from packages.db import get_session
from packages.db.models.job import ScheduledJob
from packages.db.models.tenant import Project
from packages.shared.envelope import ApiResponse
from packages.shared.errors import NotFoundError, ValidationError

router = APIRouter()


class CreateScheduledJobRequest(BaseModel):
    name: str
    cron_expression: str
    queue_id: uuid.UUID
    payload: dict | None = None


@router.post("")
async def create_scheduled_job(
    body: CreateScheduledJobRequest,
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Validate cron expression
    if not croniter.is_valid(body.cron_expression):
        raise ValidationError(f"Invalid cron expression: {body.cron_expression}")

    project = await session.scalar(
        select(Project).where(Project.organization_id == auth.org_id).limit(1)
    )
    if not project:
        raise NotFoundError("Project", "default")

    now = datetime.now(timezone.utc)
    next_run = croniter(body.cron_expression, now).get_next(datetime)

    scheduled = ScheduledJob(
        name=body.name,
        cron_expression=body.cron_expression,
        queue_id=body.queue_id,
        project_id=project.id,
        payload=body.payload,
        next_run_at=next_run,
    )
    session.add(scheduled)
    await session.flush()

    return ApiResponse.ok({
        "id": str(scheduled.id),
        "name": scheduled.name,
        "cron_expression": scheduled.cron_expression,
        "next_run_at": next_run.isoformat(),
    })


@router.get("")
async def list_scheduled_jobs(
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    project = await session.scalar(
        select(Project).where(Project.organization_id == auth.org_id).limit(1)
    )
    if not project:
        return ApiResponse.ok([])

    result = await session.execute(
        select(ScheduledJob)
        .where(ScheduledJob.project_id == project.id)
        .order_by(ScheduledJob.next_run_at.asc())
    )
    jobs = result.scalars().all()

    return ApiResponse.ok([
        {
            "id": str(j.id),
            "name": j.name,
            "cron_expression": j.cron_expression,
            "is_active": j.is_active,
            "last_run_at": j.last_run_at.isoformat() if j.last_run_at else None,
            "next_run_at": j.next_run_at.isoformat() if j.next_run_at else None,
        }
        for j in jobs
    ])

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import AuthContext, get_current_user
from packages.db import get_session
from packages.db.models.job import DeadLetterEntry, Job
from packages.shared.envelope import ApiResponse, PaginationMeta
from packages.shared.errors import NotFoundError
from packages.shared.types import JobStatus

router = APIRouter()


@router.get("")
async def list_dlq(
    is_resolved: bool | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    query = select(DeadLetterEntry)
    count_query = select(func.count(DeadLetterEntry.id))

    if is_resolved is not None:
        query = query.where(DeadLetterEntry.is_resolved == is_resolved)
        count_query = count_query.where(DeadLetterEntry.is_resolved == is_resolved)

    query = query.order_by(DeadLetterEntry.dead_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await session.execute(query)
    total = await session.scalar(count_query) or 0
    entries = result.scalars().all()

    return ApiResponse.ok(
        data=[
            {
                "id": str(e.id),
                "job_id": str(e.job_id) if e.job_id else None,
                "job_name": e.job_name,
                "last_error": e.last_error,
                "attempt_count": e.attempt_count,
                "is_resolved": e.is_resolved,
                "dead_at": e.dead_at.isoformat() if e.dead_at else None,
            }
            for e in entries
        ],
        pagination=PaginationMeta(
            page=page, per_page=per_page, total=total,
            total_pages=(total + per_page - 1) // per_page,
        ),
    )


@router.post("/{entry_id}/replay")
async def replay_dlq_entry(
    entry_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Re-enqueue a dead letter entry back to its original queue."""
    entry = await session.get(DeadLetterEntry, entry_id)
    if not entry:
        raise NotFoundError("DLQ Entry", str(entry_id))

    if entry.job_id:
        await session.execute(
            update(Job).where(Job.id == entry.job_id).values(
                status=JobStatus.QUEUED, claimed_by=None,
                last_error=None, attempt_count=0, version=Job.version + 1,
            )
        )

    from datetime import datetime, timezone
    entry.is_resolved = True
    entry.resolved_at = datetime.now(timezone.utc)
    await session.flush()
    return ApiResponse.ok({"id": str(entry_id), "replayed": True})


@router.post("/{entry_id}/resolve")
async def resolve_dlq_entry(
    entry_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    entry = await session.get(DeadLetterEntry, entry_id)
    if not entry:
        raise NotFoundError("DLQ Entry", str(entry_id))

    from datetime import datetime, timezone
    entry.is_resolved = True
    entry.resolved_at = datetime.now(timezone.utc)
    await session.flush()
    return ApiResponse.ok({"id": str(entry_id), "resolved": True})

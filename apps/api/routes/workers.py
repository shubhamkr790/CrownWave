import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import AuthContext, get_current_user
from packages.db import get_session
from packages.db.models.tenant import Project
from packages.db.models.worker import Worker, WorkerEvent
from packages.db.repositories.worker_repo import WorkerRepository
from packages.shared.envelope import ApiResponse
from packages.shared.errors import NotFoundError

router = APIRouter()


@router.get("")
async def list_workers(
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    project = await session.scalar(
        select(Project).where(Project.organization_id == auth.org_id).limit(1)
    )
    if not project:
        return ApiResponse.ok([])

    repo = WorkerRepository(session)
    workers = await repo.list_by_project(project.id)
    return ApiResponse.ok([
        {
            "id": str(w.id),
            "name": w.name,
            "status": w.status.value if hasattr(w.status, "value") else w.status,
            "queue_filter": w.queue_filter,
            "last_heartbeat_at": w.last_heartbeat_at.isoformat() if w.last_heartbeat_at else None,
            "started_at": w.started_at.isoformat() if w.started_at else None,
            "stopped_at": w.stopped_at.isoformat() if w.stopped_at else None,
        }
        for w in workers
    ])


@router.get("/{worker_id}")
async def get_worker(
    worker_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = WorkerRepository(session)
    worker = await repo.get_by_id(worker_id)
    if not worker:
        raise NotFoundError("Worker", str(worker_id))

    # Fetch recent events for this worker
    result = await session.execute(
        select(WorkerEvent)
        .where(WorkerEvent.worker_id == worker_id)
        .order_by(WorkerEvent.occurred_at.desc())
        .limit(20)
    )
    events = result.scalars().all()

    return ApiResponse.ok({
        "id": str(worker.id),
        "name": worker.name,
        "status": worker.status.value if hasattr(worker.status, "value") else worker.status,
        "queue_filter": worker.queue_filter,
        "last_heartbeat_at": worker.last_heartbeat_at.isoformat() if worker.last_heartbeat_at else None,
        "started_at": worker.started_at.isoformat() if worker.started_at else None,
        "events": [
            {
                "type": e.event_type,
                "detail": e.detail,
                "occurred_at": e.occurred_at.isoformat(),
            }
            for e in events
        ],
    })

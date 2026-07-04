import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import AuthContext, get_current_user
from packages.db import get_session
from packages.db.models.queue import Queue, RetryPolicy
from packages.db.models.tenant import Project
from packages.db.repositories.queue_repo import QueueRepository
from packages.shared.envelope import ApiResponse
from packages.shared.errors import NotFoundError

router = APIRouter()


class CreateQueueRequest(BaseModel):
    name: str
    slug: str
    description: str | None = None
    priority: int = 0
    concurrency_limit: int = 0
    retry_policy_id: uuid.UUID | None = None


class QueueResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    priority: int
    concurrency_limit: int
    is_paused: bool
    project_id: str
    created_at: str

    @classmethod
    def from_model(cls, q: Queue) -> "QueueResponse":
        return cls(
            id=str(q.id),
            name=q.name,
            slug=q.slug,
            description=q.description,
            priority=q.priority,
            concurrency_limit=q.concurrency_limit,
            is_paused=q.is_paused,
            project_id=str(q.project_id),
            created_at=q.created_at.isoformat() if q.created_at else "",
        )


@router.post("")
async def create_queue(
    body: CreateQueueRequest,
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    # Get the user's default project
    project = await session.scalar(
        select(Project).where(Project.organization_id == auth.org_id).limit(1)
    )
    if not project:
        raise NotFoundError("Project", "default")

    repo = QueueRepository(session)
    queue = Queue(
        name=body.name,
        slug=body.slug,
        description=body.description,
        priority=body.priority,
        concurrency_limit=body.concurrency_limit,
        project_id=project.id,
        retry_policy_id=body.retry_policy_id,
    )
    queue = await repo.create(queue)
    return ApiResponse.ok(QueueResponse.from_model(queue).model_dump())


@router.get("")
async def list_queues(
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    project = await session.scalar(
        select(Project).where(Project.organization_id == auth.org_id).limit(1)
    )
    if not project:
        return ApiResponse.ok([])

    repo = QueueRepository(session)
    queues = await repo.list_by_project(project.id)
    return ApiResponse.ok([QueueResponse.from_model(q).model_dump() for q in queues])


@router.get("/{queue_id}")
async def get_queue(
    queue_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = QueueRepository(session)
    queue = await repo.get_by_id(queue_id)
    if not queue:
        raise NotFoundError("Queue", str(queue_id))
    return ApiResponse.ok(QueueResponse.from_model(queue).model_dump())


@router.post("/{queue_id}/pause")
async def pause_queue(
    queue_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = QueueRepository(session)
    updated = await repo.update_pause_state(queue_id, paused=True)
    if not updated:
        raise NotFoundError("Queue", str(queue_id))
    return ApiResponse.ok({"id": str(queue_id), "is_paused": True})


@router.post("/{queue_id}/resume")
async def resume_queue(
    queue_id: uuid.UUID,
    auth: AuthContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    repo = QueueRepository(session)
    updated = await repo.update_pause_state(queue_id, paused=False)
    if not updated:
        raise NotFoundError("Queue", str(queue_id))
    return ApiResponse.ok({"id": str(queue_id), "is_paused": False})

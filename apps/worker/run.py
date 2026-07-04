import asyncio
import os
import sys
import uuid

from apps.worker.process import WorkerProcess

DEFAULT_PROJECT_ID = "00000000-0000-0000-0000-000000000001"

async def get_latest_project_id() -> uuid.UUID:
    try:
        from packages.db.session import async_session_factory
        from packages.db.models.tenant import Project
        from sqlalchemy import select
        async with async_session_factory() as session:
            project = await session.scalar(select(Project).order_by(Project.created_at.desc()).limit(1))
            if project:
                return project.id
    except Exception as e:
        print(f"Failed to fetch latest project: {e}")
    return uuid.UUID(DEFAULT_PROJECT_ID)

async def start_worker():
    project_id_str = os.environ.get("PROJECT_ID")
    if len(sys.argv) > 1:
        project_id_str = sys.argv[1]
    
    if project_id_str:
        project_id = uuid.UUID(project_id_str)
    else:
        project_id = await get_latest_project_id()
        
    print(f"Starting worker for project: {project_id}")
    worker = WorkerProcess(project_id=project_id)
    await worker.start()

def main():
    asyncio.run(start_worker())

if __name__ == "__main__":
    main()

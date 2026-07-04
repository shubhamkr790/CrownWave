import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.routes import auth, jobs, queues, workers, metrics, dlq, scheduled
from packages.config import get_settings
from packages.logging import configure_logging, get_logger
from packages.shared.errors import CronwaveError

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure structlog
    configure_logging()
    
    settings = get_settings()
    log.info("api_starting", environment=settings.environment, port=settings.api_port)
    yield
    log.info("api_shutting_down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Cronwave",
        description="Distributed job scheduler API",
        version="0.4.1",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    # -- Middleware --
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        structlog.contextvars.unbind_contextvars("request_id")
        return response

    # -- CORS --
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


    # -- Domain error handler --
    @app.exception_handler(CronwaveError)
    async def domain_error_handler(request: Request, exc: CronwaveError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": exc.message,
                "error_code": exc.error_code,
            },
        )

    # -- Generic exception handler --
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected errors globally."""
        log.exception(
            "Unhandled exception",
            exc_info=exc,
            path=request.url.path,
            method=request.method,
            client_ip=request.client.host if request.client else None
        )
        return JSONResponse(
            status_code=500,
            content={"error": {"message": "Internal server error"}},
        )

    # -- Routes --
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])
    app.include_router(queues.router, prefix="/api/v1/queues", tags=["queues"])
    app.include_router(workers.router, prefix="/api/v1/workers", tags=["workers"])
    app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["metrics"])
    app.include_router(dlq.router, prefix="/api/v1/dlq", tags=["dead-letter-queue"])
    app.include_router(scheduled.router, prefix="/api/v1/scheduled-jobs", tags=["scheduled-jobs"])

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": "0.4.1"}

    return app


app = create_app()

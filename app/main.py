from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import APIRouter, FastAPI, Request, Response

from app.agent.factory import build_coding_agent
from app.agent.service import CodingAgentService, InMemorySessionStore
from app.api.routes.agent import router as agent_router
from app.api.routes.health import router as health_router
from app.core.config import Settings, load_settings
from app.core.observability import configure_observability


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        configure_observability(resolved_settings)
        session_store = InMemorySessionStore(
            ttl_seconds=resolved_settings.session_ttl_seconds,
            max_sessions=resolved_settings.session_max_count,
        )
        application.state.settings = resolved_settings
        application.state.agent_service = CodingAgentService(
            agent=build_coding_agent(resolved_settings),
            settings=resolved_settings,
            session_store=session_store,
        )
        yield

    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )

    @application.middleware("http")
    async def add_request_id(request: Request, call_next) -> Response:
        request_id = _request_id(request.headers.get("X-Request-ID"))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    root_router = APIRouter()

    @root_router.get("/", tags=["metadata"])
    async def root() -> dict[str, str]:
        return {
            "name": resolved_settings.app_name,
            "version": resolved_settings.app_version,
            "docs": "/docs",
        }

    application.include_router(root_router)
    application.include_router(health_router)
    application.include_router(agent_router, prefix="/api/v1")
    return application


def _request_id(value: str | None) -> str:
    if value is not None:
        try:
            return str(UUID(value))
        except ValueError:
            pass
    return str(uuid4())


app = create_app()


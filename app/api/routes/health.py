from fastapi import APIRouter, Request, Response, status

from app.schemas import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=HealthResponse)
async def readiness(request: Request, response: Response) -> HealthResponse:
    service = getattr(request.app.state, "agent_service", None)
    if service is None or not service.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="not_ready")
    return HealthResponse(status="ready")


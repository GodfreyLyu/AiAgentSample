import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.agent.service import CodingAgentService
from app.core.config import Settings

bearer_scheme = HTTPBearer(auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_agent_service(request: Request) -> CodingAgentService:
    return request.app.state.agent_service


async def require_api_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Require a bearer token when API_BEARER_TOKEN is configured."""
    configured_token = settings.api_bearer_token
    if configured_token is None:
        return

    supplied_token = credentials.credentials if credentials else ""
    if not secrets.compare_digest(configured_token.get_secret_value(), supplied_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


ProtectedEndpoint = Annotated[None, Depends(require_api_token)]
AgentService = Annotated[CodingAgentService, Depends(get_agent_service)]


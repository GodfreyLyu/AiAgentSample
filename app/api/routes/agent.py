import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.agent.service import AgentRunTimeoutError, SessionCapacityError
from app.api.dependencies import AgentService, ProtectedEndpoint
from app.schemas import ChatRequest, ChatResponse, DeleteSessionResponse, UsageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    service: AgentService,
    _: ProtectedEndpoint,
) -> ChatResponse:
    try:
        result = await service.chat(payload.message, payload.session_id)
    except SessionCapacityError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except AgentRunTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Agent run failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The model provider could not complete the request.",
        ) from exc

    return ChatResponse(
        session_id=result.session_id,
        output=result.output,
        usage=UsageResponse(
            requests=result.usage.requests,
            tool_calls=result.usage.tool_calls,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
        ),
    )


@router.delete("/sessions/{session_id}", response_model=DeleteSessionResponse)
async def delete_session(
    session_id: UUID,
    service: AgentService,
    _: ProtectedEndpoint,
) -> DeleteSessionResponse:
    deleted = await service.delete_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )
    return DeleteSessionResponse(session_id=session_id, deleted=True)


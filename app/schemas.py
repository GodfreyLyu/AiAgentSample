from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=20_000)
    session_id: UUID | None = None


class UsageResponse(BaseModel):
    requests: int
    tool_calls: int
    input_tokens: int
    output_tokens: int


class ChatResponse(BaseModel):
    session_id: UUID
    output: str
    usage: UsageResponse


class DeleteSessionResponse(BaseModel):
    session_id: UUID
    deleted: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "ready", "not_ready"]


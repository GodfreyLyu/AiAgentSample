import asyncio
import os
from dataclasses import dataclass, field
from time import monotonic
from uuid import UUID, uuid4

from pydantic_ai import Agent, UsageLimits
from pydantic_ai.messages import ModelMessage

from app.agent.dependencies import AgentDependencies
from app.core.config import Settings


class SessionCapacityError(RuntimeError):
    """Raised when the in-memory session store reaches its configured capacity."""


class AgentRunTimeoutError(TimeoutError):
    """Raised when a complete agent run exceeds its configured deadline."""


@dataclass(slots=True)
class SessionRecord:
    history: list[ModelMessage] = field(default_factory=list)
    expires_at: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class InMemorySessionStore:
    """Concurrency-safe, process-local message history storage with expiration."""

    def __init__(self, ttl_seconds: int, max_sessions: int) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_sessions = max_sessions
        self._records: dict[UUID, SessionRecord] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, session_id: UUID) -> SessionRecord:
        async with self._lock:
            now = monotonic()
            expired_ids = [
                key for key, record in self._records.items() if record.expires_at <= now
            ]
            for key in expired_ids:
                self._records.pop(key, None)

            record = self._records.get(session_id)
            if record is not None:
                record.expires_at = now + self._ttl_seconds
                return record

            if len(self._records) >= self._max_sessions:
                raise SessionCapacityError("The session store is at capacity.")

            record = SessionRecord(expires_at=now + self._ttl_seconds)
            self._records[session_id] = record
            return record

    async def touch(self, record: SessionRecord) -> None:
        record.expires_at = monotonic() + self._ttl_seconds

    async def delete(self, session_id: UUID) -> bool:
        async with self._lock:
            return self._records.pop(session_id, None) is not None


@dataclass(frozen=True, slots=True)
class UsageSnapshot:
    requests: int
    tool_calls: int
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class AgentChatResult:
    session_id: UUID
    output: str
    usage: UsageSnapshot


class CodingAgentService:
    """Coordinate agent runs, session history, limits, and per-pod concurrency."""

    def __init__(
        self,
        agent: Agent[AgentDependencies, str],
        settings: Settings,
        session_store: InMemorySessionStore,
    ) -> None:
        settings.agent_workspace_root.mkdir(parents=True, exist_ok=True)
        self._agent = agent
        self._settings = settings
        self._session_store = session_store
        self._semaphore = asyncio.Semaphore(settings.agent_max_concurrency)
        self._deps = AgentDependencies(
            workspace_root=settings.agent_workspace_root,
            allowed_commands=frozenset(settings.agent_allowed_commands),
            command_enabled=settings.agent_command_enabled,
            command_timeout_seconds=settings.agent_command_timeout_seconds,
            max_file_size_bytes=settings.agent_max_file_size_bytes,
            max_command_output_chars=settings.agent_max_command_output_chars,
        )

    @property
    def ready(self) -> bool:
        workspace = self._deps.workspace_root
        return workspace.is_dir() and os.access(workspace, os.R_OK | os.W_OK | os.X_OK)

    async def chat(self, message: str, session_id: UUID | None = None) -> AgentChatResult:
        resolved_session_id = session_id or uuid4()
        record = await self._session_store.get_or_create(resolved_session_id)
        limits = UsageLimits(
            request_limit=self._settings.agent_request_limit,
            tool_calls_limit=self._settings.agent_tool_calls_limit,
            total_tokens_limit=self._settings.agent_total_tokens_limit,
        )

        async with self._semaphore, record.lock:
            try:
                async with asyncio.timeout(self._settings.agent_run_timeout_seconds):
                    result = await self._agent.run(
                        message,
                        deps=self._deps,
                        message_history=list(record.history),
                        usage_limits=limits,
                    )
            except TimeoutError as exc:
                raise AgentRunTimeoutError(
                    "The agent run exceeded its configured deadline."
                ) from exc

            record.history = result.all_messages()
            await self._session_store.touch(record)
            usage = result.usage
            return AgentChatResult(
                session_id=resolved_session_id,
                output=result.output,
                usage=UsageSnapshot(
                    requests=usage.requests,
                    tool_calls=usage.tool_calls,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                ),
            )

    async def delete_session(self, session_id: UUID) -> bool:
        return await self._session_store.delete(session_id)


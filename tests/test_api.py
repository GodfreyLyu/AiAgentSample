from uuid import UUID

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.agent.service import AgentChatResult, UsageSnapshot
from app.core.config import Settings
from app.main import create_app


class FakeAgentService:
    ready = True

    async def chat(self, message: str, session_id: UUID | None) -> AgentChatResult:
        return AgentChatResult(
            session_id=session_id or UUID("11111111-1111-1111-1111-111111111111"),
            output=f"Processed: {message}",
            usage=UsageSnapshot(
                requests=1,
                tool_calls=0,
                input_tokens=5,
                output_tokens=3,
            ),
        )

    async def delete_session(self, session_id: UUID) -> bool:
        return session_id == UUID("11111111-1111-1111-1111-111111111111")


def test_health_and_chat_endpoints(tmp_path) -> None:
    settings = Settings(
        deepseek_api_key=SecretStr("test-key"),
        api_bearer_token=SecretStr("test-token"),
        agent_workspace_root=tmp_path,
        environment="test",
    )
    application = create_app(settings)

    with TestClient(application) as client:
        application.state.agent_service = FakeAgentService()

        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/health/ready").json() == {"status": "ready"}

        unauthorized = client.post("/api/v1/agent/chat", json={"message": "Hello"})
        assert unauthorized.status_code == 401

        response = client.post(
            "/api/v1/agent/chat",
            headers={"Authorization": "Bearer test-token"},
            json={"message": "Hello"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "11111111-1111-1111-1111-111111111111",
        "output": "Processed: Hello",
        "usage": {
            "requests": 1,
            "tool_calls": 0,
            "input_tokens": 5,
            "output_tokens": 3,
        },
    }
    assert UUID(response.headers["X-Request-ID"])


def test_chat_rejects_blank_message(tmp_path) -> None:
    settings = Settings(
        deepseek_api_key=SecretStr("test-key"),
        api_bearer_token=None,
        agent_workspace_root=tmp_path,
        environment="test",
    )
    application = create_app(settings)

    with TestClient(application) as client:
        application.state.agent_service = FakeAgentService()
        response = client.post("/api/v1/agent/chat", json={"message": "   "})

    assert response.status_code == 422

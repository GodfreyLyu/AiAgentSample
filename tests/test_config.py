from pydantic import SecretStr

from app.core.config import Settings


def test_settings_parse_command_allowlist(tmp_path) -> None:
    settings = Settings(
        deepseek_api_key=SecretStr("test-key"),
        agent_workspace_root=tmp_path,
        agent_allowed_commands="python, pytest,ruff",
    )

    assert settings.agent_allowed_commands == ("python", "pytest", "ruff")
    assert settings.agent_workspace_root == tmp_path.resolve()


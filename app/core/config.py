from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    app_name: str = "AI Agent API"
    app_version: str = "0.1.0"
    environment: Literal["local", "test", "staging", "production"] = "local"
    log_level: str = "INFO"
    api_bearer_token: SecretStr | None = None

    deepseek_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("DP_API_KEY", "DEEPSEEK_API_KEY"),
    )
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_api_mode: Literal["responses", "chat"] = "responses"

    agent_workspace_root: Path = Path("workspace")
    agent_command_enabled: bool = False
    agent_allowed_commands: Annotated[tuple[str, ...], NoDecode] = (
        "python",
        "python3",
        "pytest",
        "ruff",
    )
    agent_command_timeout_seconds: float = Field(default=10.0, gt=0, le=300)
    agent_run_timeout_seconds: float = Field(default=120.0, gt=0, le=900)
    agent_max_file_size_bytes: int = Field(default=1_000_000, gt=0)
    agent_max_command_output_chars: int = Field(default=50_000, gt=0)
    agent_request_limit: int = Field(default=12, gt=0, le=100)
    agent_tool_calls_limit: int = Field(default=30, gt=0, le=500)
    agent_total_tokens_limit: int = Field(default=80_000, gt=0)
    agent_max_concurrency: int = Field(default=10, gt=0, le=100)

    session_ttl_seconds: int = Field(default=3600, gt=0)
    session_max_count: int = Field(default=1000, gt=0)
    logfire_send_to_logfire: bool = False

    @field_validator("agent_workspace_root", mode="before")
    @classmethod
    def resolve_workspace_root(cls, value: object) -> Path:
        return Path(str(value)).expanduser().resolve()

    @field_validator("agent_allowed_commands", mode="before")
    @classmethod
    def parse_allowed_commands(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return value

    @field_validator("agent_allowed_commands")
    @classmethod
    def validate_allowed_commands(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        invalid = [command for command in value if Path(command).name != command]
        if invalid:
            raise ValueError("Allowed commands must be executable names, not paths.")
        return value

    def require_deepseek_api_key(self) -> str:
        if self.deepseek_api_key is None:
            raise RuntimeError(
                "Set DP_API_KEY or DEEPSEEK_API_KEY before starting the application."
            )
        return self.deepseek_api_key.get_secret_value()


@lru_cache
def load_settings() -> Settings:
    return Settings()


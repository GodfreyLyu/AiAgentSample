from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AgentDependencies:
    """Runtime values exposed to the agent tools."""

    workspace_root: Path
    allowed_commands: frozenset[str]
    command_enabled: bool
    command_timeout_seconds: float
    max_file_size_bytes: int
    max_command_output_chars: int


import asyncio
import os
import shlex
from pathlib import Path

from pydantic_ai import RunContext

from app.agent.dependencies import AgentDependencies


class WorkspaceAccessError(ValueError):
    """Raised when a tool attempts to access a path outside its workspace."""


def resolve_workspace_path(deps: AgentDependencies, path: str) -> Path:
    """Resolve a user-supplied path and keep it inside the configured workspace."""
    if not path or "\x00" in path:
        raise WorkspaceAccessError("A non-empty, valid path is required.")

    root = deps.workspace_root.resolve()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise WorkspaceAccessError(
            f"Path '{path}' is outside the agent workspace."
        ) from exc
    return candidate


def read_workspace_file(deps: AgentDependencies, path: str) -> str:
    """Read a UTF-8 text file from the agent workspace."""
    try:
        target = resolve_workspace_path(deps, path)
        if not target.exists():
            return f"Error: file '{path}' does not exist."
        if not target.is_file():
            return f"Error: path '{path}' is not a regular file."
        if target.stat().st_size > deps.max_file_size_bytes:
            return (
                f"Error: file '{path}' exceeds the "
                f"{deps.max_file_size_bytes}-byte read limit."
            )
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeError, WorkspaceAccessError) as exc:
        return f"Error: unable to read '{path}': {exc}"


def write_workspace_file(deps: AgentDependencies, path: str, content: str) -> str:
    """Write UTF-8 text to a file inside the agent workspace."""
    try:
        encoded = content.encode("utf-8")
        if len(encoded) > deps.max_file_size_bytes:
            return (
                f"Error: content exceeds the {deps.max_file_size_bytes}-byte write limit."
            )

        target = resolve_workspace_path(deps, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        relative_path = target.relative_to(deps.workspace_root.resolve())
        return f"Wrote {len(encoded)} bytes to '{relative_path}'."
    except (OSError, UnicodeError, WorkspaceAccessError) as exc:
        return f"Error: unable to write '{path}': {exc}"


async def run_workspace_command(deps: AgentDependencies, command: str) -> str:
    """Run an allowlisted executable without invoking a shell."""
    if not deps.command_enabled:
        return "Error: command execution is disabled by configuration."

    try:
        arguments = shlex.split(command)
    except ValueError as exc:
        return f"Error: invalid command syntax: {exc}"

    if not arguments:
        return "Error: a non-empty command is required."

    executable = arguments[0]
    if Path(executable).name != executable:
        return "Error: executable paths are not allowed; use an allowlisted command name."
    if executable not in deps.allowed_commands:
        allowed = ", ".join(sorted(deps.allowed_commands)) or "none"
        return f"Error: command '{executable}' is not allowed. Allowed commands: {allowed}."

    process_environment = {
        "LANG": "C.UTF-8",
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "PYTHONUNBUFFERED": "1",
    }

    try:
        process = await asyncio.create_subprocess_exec(
            *arguments,
            cwd=deps.workspace_root,
            env=process_environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        return f"Error: unable to start command: {exc}"

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=deps.command_timeout_seconds,
        )
    except TimeoutError:
        process.kill()
        await process.communicate()
        return (
            "Error: command timed out after "
            f"{deps.command_timeout_seconds:g} seconds."
        )

    sections: list[str] = []
    stdout_text = stdout.decode("utf-8", errors="replace").strip()
    stderr_text = stderr.decode("utf-8", errors="replace").strip()
    if stdout_text:
        sections.append(stdout_text)
    if stderr_text:
        sections.append(f"[stderr]\n{stderr_text}")
    if process.returncode:
        sections.append(f"[exit code: {process.returncode}]")

    output = "\n".join(sections) or "(no output)"
    if len(output) > deps.max_command_output_chars:
        omitted = len(output) - deps.max_command_output_chars
        output = (
            output[: deps.max_command_output_chars]
            + f"\n[output truncated; {omitted} characters omitted]"
        )
    return output


def read_file(ctx: RunContext[AgentDependencies], path: str) -> str:
    """Read the contents of a UTF-8 text file in the coding workspace.

    Args:
        path: A path relative to the coding workspace.
    """
    return read_workspace_file(ctx.deps, path)


def write_file(ctx: RunContext[AgentDependencies], path: str, content: str) -> str:
    """Write content to a UTF-8 text file in the coding workspace.

    Args:
        path: A path relative to the coding workspace.
        content: The complete text to write.
    """
    return write_workspace_file(ctx.deps, path, content)


async def run_command(ctx: RunContext[AgentDependencies], command: str) -> str:
    """Run an allowlisted command in the coding workspace and return its output.

    Shell operators, pipelines, and executable paths are not supported.

    Args:
        command: The executable name followed by its arguments.
    """
    return await run_workspace_command(ctx.deps, command)


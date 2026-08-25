from app.agent.dependencies import AgentDependencies
from app.agent.tools import read_workspace_file, write_workspace_file


def make_dependencies(tmp_path) -> AgentDependencies:
    return AgentDependencies(
        workspace_root=tmp_path,
        allowed_commands=frozenset({"python"}),
        command_enabled=False,
        command_timeout_seconds=1,
        max_file_size_bytes=1000,
        max_command_output_chars=1000,
    )


def test_tools_read_and_write_inside_workspace(tmp_path) -> None:
    dependencies = make_dependencies(tmp_path)

    write_result = write_workspace_file(dependencies, "src/example.py", "print('ok')\n")
    read_result = read_workspace_file(dependencies, "src/example.py")

    assert write_result == "Wrote 12 bytes to 'src/example.py'."
    assert read_result == "print('ok')\n"


def test_tools_reject_path_traversal(tmp_path) -> None:
    dependencies = make_dependencies(tmp_path)

    result = write_workspace_file(dependencies, "../outside.txt", "blocked")

    assert result.startswith("Error: unable to write")
    assert "outside the agent workspace" in result


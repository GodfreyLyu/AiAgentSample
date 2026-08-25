from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
from pydantic_ai.providers.deepseek import DeepSeekProvider

from app.agent.dependencies import AgentDependencies
from app.agent.tools import read_file, run_command, write_file
from app.core.config import Settings

AGENT_INSTRUCTIONS = """\
You are a programming assistant. You can read and write files and run approved commands to
help the user complete programming tasks.

Workflow:
1. Understand the request and inspect the relevant files.
2. Make focused code changes that follow the existing project conventions.
3. Run the available checks or tests.
4. If a check fails, diagnose the failure, fix it, and rerun the check.
5. Finish with a concise summary of the changes and verification performed.

All file operations are limited to the configured workspace. Never claim that a file was
changed or a command succeeded unless the corresponding tool result confirms it.
"""


def build_coding_agent(settings: Settings) -> Agent[AgentDependencies, str]:
    """Build the Pydantic AI coding agent from application settings."""
    api_key = settings.require_deepseek_api_key()
    provider = DeepSeekProvider(api_key=api_key)

    if settings.deepseek_api_mode == "responses":
        model = OpenAIResponsesModel(settings.deepseek_model, provider=provider)
    else:
        model = OpenAIChatModel(settings.deepseek_model, provider=provider)

    return Agent(
        model,
        deps_type=AgentDependencies,
        instructions=AGENT_INSTRUCTIONS,
        name="coding_agent",
        tools=[read_file, write_file, run_command],
    )


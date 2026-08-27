# AI Agent Sample

A FastAPI service that exposes a Pydantic AI coding agent backed by DeepSeek. The service
keeps multi-turn context by session, restricts file access to a configured workspace, and
runs only allowlisted executables without a shell.

## Project layout

```text
app/
  agent/          Agent factory, tools, session store, and orchestration
  api/routes/     Versioned agent and health endpoints
  core/           Environment configuration and observability
  main.py         FastAPI application factory
deploy/            Kustomize base and Minikube/EKS overlays
tests/            API, configuration, and workspace boundary tests
Dockerfile        Non-root container image for deployment
```

## Local setup

Python 3.12 or later is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
cp .env.example .env
```

Set a real `DP_API_KEY` in `.env`, then start the API:

```bash
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API documentation.

## API usage

Start a conversation:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/agent/chat \
  -H "Authorization: Bearer replace-with-a-long-random-token" \
  -H "Content-Type: application/json" \
  -d '{"message":"Create a Python function that validates an email address."}'
```

The response includes a `session_id`. Include that value in later requests to preserve the
conversation history:

```json
{
  "message": "Now add unit tests.",
  "session_id": "11111111-1111-1111-1111-111111111111"
}
```

Delete stored history with `DELETE /api/v1/agent/sessions/{session_id}`.

## Configuration

`DP_API_KEY` and `DEEPSEEK_API_KEY` are both accepted. The default model is
`deepseek-v4-flash`, which uses DeepSeek's Responses-compatible API. Set
`DEEPSEEK_API_MODE=chat` when choosing a model that requires Chat Completions.

Command execution is disabled by default in application settings. The example environment
enables it for local development and limits executables with `AGENT_ALLOWED_COMMANDS`.
Shell expansion, pipelines, executable paths, and shell operators are not supported.

## Verification

```bash
ruff check .
pytest
```

## Container and EKS notes

Build and run the same non-root image that will be deployed to EKS:

```bash
docker build -t ai-agent-sample:local .
docker run --rm -p 8000:8000 \
  -e DP_API_KEY="your-key" \
  -e API_BEARER_TOKEN="your-token" \
  -e AGENT_WORKSPACE_ROOT=/workspace \
  ai-agent-sample:local
```

Use `/health/live` for the Kubernetes liveness probe and `/health/ready` for readiness.
Provide secrets through AWS Secrets Manager or Kubernetes Secrets, run with a read-only root
filesystem, disable service-account token mounting unless it is required, and apply a network
policy appropriate for the model endpoint.

The repository includes a hardened Kustomize base plus Minikube and EKS overlays. The EKS
overlay uses an ALB Ingress and External Secrets Operator, while GitHub Actions tests the
service, builds an immutable ECR image, and performs a verified rolling deployment with AWS
OIDC credentials. See the [Kubernetes deployment guide](deploy/README.md) for details.

The current conversation store is in memory. It is suitable for local development and a
single replica. Before scaling across EKS replicas, implement the existing session-store
boundary with a shared backend such as ElastiCache for Redis. The coding workspace is also
pod-local; use an isolated ephemeral volume per workload and do not mount infrastructure
credentials into a pod that has command execution enabled.

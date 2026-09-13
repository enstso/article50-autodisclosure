# Article 50 AutoDisclosure

> An autonomous AI engineering agent that finds and fixes missing AI transparency disclosures before release.

## Product

Article 50 AutoDisclosure is a developer tool for finding missing transparency disclosures in AI-powered applications before they are released.

## Problem

Developers increasingly ship AI-powered features, but user-facing AI interactions may lack appropriate transparency notices.

## Solution

The future agent will:

```text
Detect
→ Investigate
→ Explain
→ Remediate
→ Human Approve
→ Verify
```

The current proof of concept securely clones a public GitHub repository and lets Strands agents
investigate its architecture and reconstruct evidence-backed, user-facing AI interaction paths through
bounded read-only tools. Article 50 decisions and remediation are intentionally not implemented yet.

## Stack

- React, TypeScript, Vite, Tailwind CSS, and React Router
- FastAPI, Pydantic v2, pydantic-settings, GitPython, and boto3 on Python 3.12+
- Strands Agents SDK with validated Pydantic structured output
- Amazon Bedrock using Claude Sonnet 4.6

## Development

### Backend

From the repository root, create a Python 3.12 virtual environment, install the backend, and start the API:

```powershell
py -3.12 -m venv backend/.venv
backend/.venv/Scripts/Activate.ps1
python -m pip install -e "./backend[dev]"
Copy-Item backend/.env.example backend/.env
uvicorn app.main:app --reload --app-dir backend
```

The API is available at `http://localhost:8000`; its health endpoint is `http://localhost:8000/api/health`.

### Frontend

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` requests to the local backend, so the page should display **API Connected** when both processes are running.

To target a different API, copy the root `.env.example` to `frontend/.env` and set `VITE_API_BASE_URL` to its origin (for example, `http://localhost:8000`).

### Verification

```powershell
cd backend
pytest

cd ../frontend
npm run build
```

## Configuration

Backend settings are read from environment variables or `backend/.env`. AWS credentials are not
application settings: boto3 uses its standard credential provider chain, including AWS CLI profiles,
runtime environment credentials, and IAM roles. Never add AWS keys to an `.env` file.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `development` | Runtime environment |
| `AWS_REGION` | `us-east-1` | Future Bedrock region |
| `BEDROCK_MODEL_ID` | `global.anthropic.claude-sonnet-4-6` | Bedrock model identifier |
| `WORKSPACE_PATH` | `./workspace` | Isolated repository workspaces |
| `MAX_REPOSITORY_SIZE_MB` | `50` | Maximum cloned repository size |
| `MAX_FILE_SIZE_KB` | `250` | Maximum source content loaded by a tool |

## Repository analysis API

Start a synchronous proof-of-concept scan:

```http
POST /api/scans
Content-Type: application/json

{"repository_url":"https://github.com/owner/repository"}
```

Retrieve the stored result with `GET /api/scans/{scan_id}`. Scan results are held in memory and are
lost when the API process restarts.

Completed scans contain:

- a general `summary` of languages, frameworks, architecture, and important files;
- deterministic and agent-validated `ai_usages`;
- confirmed or partial `ai_interactions` with UI, endpoint, handler, provider, model, confidence, and
  source evidence;
- short operational `events` without model chain-of-thought.

Only public `https://github.com/{owner}/{repository}` URLs are accepted. Each scan gets an isolated
workspace, cloning is shallow, and cloned code is never executed. Repository tools only list, read,
and search bounded text content; ignored build/dependency directories and paths outside the repository
cannot be accessed.

AI detection combines dependency manifests, bounded source-pattern matching, API route discovery,
endpoint caller search, symbol references, and progressive Strands investigation. Dependencies and
README mentions remain signals only. Before results reach the API, every model-proposed evidence item
is checked against the real repository-relative file and line and replaced with the canonical source
snippet. A user-facing flow requires evidence for the client caller, API route, backend link, and model
invocation.

## AWS status

The real Strands-to-Bedrock integration is implemented. Automated tests replace the agent and clone
operations with local fakes, so they need neither AWS credentials nor network access. Live Bedrock
validation may remain pending while the AWS account is under verification.

See [docs/architecture.md](docs/architecture.md) for the initial module boundaries.

## License

Licensed under the [MIT License](LICENSE).

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

This first version provides only the application foundation. Repository analysis and remediation are intentionally not implemented yet.

## Stack

- React, TypeScript, Vite, Tailwind CSS, and React Router
- FastAPI, Pydantic v2, and pydantic-settings on Python 3.12+
- Strands Agents SDK — upcoming
- Amazon Bedrock — upcoming

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

Backend settings are read from environment variables or `backend/.env`. AWS credentials are not application settings and must use the standard AWS credential provider chain when AWS support is added.

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_ENV` | `development` | Runtime environment |
| `AWS_REGION` | `us-east-1` | Future Bedrock region |
| `BEDROCK_MODEL_ID` | empty | Future Bedrock model identifier |
| `WORKSPACE_PATH` | `./workspace` | Future repository workspace |

See [docs/architecture.md](docs/architecture.md) for the initial module boundaries.

## License

Licensed under the [MIT License](LICENSE).


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

The current proof of concept securely clones a public GitHub repository, reconstructs evidence-backed
user-facing AI interaction paths, and assesses whether a relevant AI transparency disclosure appears
in the interface. For eligible findings, it can generate and validate a minimal patch proposal for
explicit human approval, safely apply it to the isolated workspace, and re-run the targeted Article 50
assessment.

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

For a deterministic presentation flow, choose **Try Demo Repository**, then **Analyze Repository**.
The controlled local fixture uses the real scan, proposal validation, approval, patch application,
and verification services with mocked model responses. The UI labels this state **Mock model
enabled**; ordinary public GitHub scans remain configured for Amazon Bedrock.

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
| `MAX_PATCH_LINES` | `120` | Maximum unified-diff size accepted for review |

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
- evidence-backed `article50_assessments` using `PASS`, `ACTION_REQUIRED`, or `NEEDS_REVIEW`;
- `findings` for potential transparency gaps and cases that need manual review;
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

Article 50 readiness uses one centralized MVP rule,
`ARTICLE_50_1_AI_INTERACTION_DISCLOSURE`. Deterministic heuristics first inspect the confirmed
interaction entrypoint, directly related UI components, parent components, and easily discoverable
translations. Only rendered UI text and user-visible attributes are candidates. README text, comments,
variable names, backend logs, dependencies, and unrelated AI mentions cannot produce a passing result.
The Article 50 Strands agent receives those bounded candidates and read-only inspection tools; a final
validator rechecks disclosure evidence against the repository before generating assessments and
findings.

`PASS` means a clear, relevant disclosure was detected. `ACTION_REQUIRED` identifies a potential
transparency gap in a confirmed user-facing interaction. `NEEDS_REVIEW` is used when the flow, text, or
visibility is ambiguous. Confidence represents evidence completeness, not a probability of legal
compliance. The product provides a readiness assessment and does not provide legal advice or certify
compliance.

## Remediation proposal API

Only an `ACTION_REQUIRED` finding for `ARTICLE_50_1_AI_INTERACTION_DISCLOSURE` with a verified frontend
entrypoint exposes `remediation_available=true`. Generate its proposal with:

```http
POST /api/findings/{finding_id}/patch
```

Retrieve it with `GET /api/patches/{patch_id}`, then record a human decision with either:

```http
POST /api/patches/{patch_id}/approve
POST /api/patches/{patch_id}/reject
```

The reject endpoint optionally accepts `{"reason":"..."}`. Approval records the human decision but
still does not mutate source. Apply an approved proposal with:

```http
POST /api/patches/{patch_id}/apply
```

Only `APPROVED` patches can enter `APPLYING → APPLIED → VERIFIED`; an applied or verified patch cannot
be applied twice. The response includes a stored verification result with the previous and new
readiness states, disclosure evidence, and `PASSED`, `FAILED`, or `NEEDS_REVIEW`.
The same result can be restored after a page refresh with
`GET /api/patches/{patch_id}/verification`.

The scan service retains an isolated workspace only when a safe remediation is available. The
remediation agent sees a bounded source snapshot through one read-only tool.
Its unified diff is dry-applied in memory and rejected unless paths are safe, the target is the allowed
existing frontend file, hunks match the original source, the explicit disclosure is rendered as visible
UI text, and the configured line limit is respected.

Application repeats every validation against the current file, rejects stale sources, traversal,
absolute paths, `.git`, binary data, oversized patches, and files outside `affected_files`, then creates
`workspace/{scan_id}/snapshots/{patch_id}` containing only the affected file. A deterministic Python
applicator writes no other path; repository-wide before/after hashes detect unexpected mutations. Any
failure after mutation restores the snapshot and marks the patch `FAILED`.

After a successful write, the existing Article 50 analyzer re-evaluates only the affected interaction.
`ACTION_REQUIRED → PASS` yields `VERIFIED` and resolves the finding. A remaining gap keeps the patch
`APPLIED`, the scan `ACTION_REQUIRED`, and records failed verification. No cloned dependency is
installed, and no repository code, scripts, tests, shell commands, Git commit, or push are executed.
Scan, patch, and verification records are process-local and are lost when the API restarts; retained
workspaces currently require operational lifecycle cleanup.

## AWS status

The real Strands-to-Bedrock integration is implemented for repository, interaction, Article 50, and
remediation analysis. Targeted post-application verification reuses that Article 50 analysis boundary.
Automated tests replace agent and clone operations with local fakes, so they need neither AWS credentials
nor network access. Live Bedrock validation may remain pending while the AWS account is under
verification.

See [docs/architecture.md](docs/architecture.md) for the initial module boundaries.

## License

Licensed under the [MIT License](LICENSE).

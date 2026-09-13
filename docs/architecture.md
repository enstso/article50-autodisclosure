# Initial architecture

Article 50 AutoDisclosure is split into independently runnable frontend and backend applications.

```text
Browser (React)
    │ POST /api/scans, GET /api/scans/{id}
    ▼
FastAPI application
    ├── api       HTTP routes and schemas
    ├── core      configuration and cross-cutting concerns
    ├── models    workflow domain models
    ├── services  scan, workspace, and shallow-clone orchestration
    ├── agents    Strands repository and AI interaction investigators
    └── tools     bounded repository, AI, route, endpoint, and symbol inspection
```

## Repository investigation flow

```text
Validate GitHub HTTPS URL
→ create workspace/{scan_id}/repository
→ shallow clone without submodules, tags, prompts, or LFS smudge
→ enforce repository size limit
→ invoke Strands with the centralized Bedrock model
→ validate RepositorySummary with Pydantic
→ detect deterministic AI signals and routes
→ let the AI interaction agent investigate targeted source paths
→ verify every proposed evidence item against actual files and lines
→ calibrate confidence from UI/API/backend/model evidence completeness
→ retain the scan result in memory
→ remove the temporary workspace
```

The agent receives no shell or file-write tool. The only available operations are structure discovery,
directory listing, bounded UTF-8 source reading, and bounded literal text search. All paths are resolved
and checked against the backend-generated repository root, and shared rules exclude dependency, build,
cache, IDE, and Git metadata directories.

AWS model creation lives in `app/core/bedrock.py`. It receives only the configured model identifier and
region; boto3 resolves credentials through its standard provider chain. Tests inject fake clone and agent
implementations and never contact GitHub or AWS.

## Evidence boundary

The language model proposes architecture conclusions, but it is not trusted as a source of code facts.
`EvidenceService` re-opens each proposed repository-relative file, validates its line number and exact
snippet, and emits the canonical source line. Deterministic AI candidates, route locations, and endpoint
callers provide additional allowlists for evidence types. Unsupported or fabricated evidence is dropped.

An installed dependency alone can appear as a detector signal but cannot become a confirmed interaction.
A confirmed user-facing interaction requires evidence spanning a client endpoint call, an API route, a
backend handler/service link, and an actual model invocation. Incomplete or background-only usage remains
an `AIUsage` without an invented frontend connection.

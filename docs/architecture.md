# Initial architecture

Article 50 AutoDisclosure is split into independently runnable frontend and backend applications.

```text
Browser (React)
    │ scan, patch generation, review, approval, and rejection endpoints
    ▼
FastAPI application
    ├── api       HTTP routes and schemas
    ├── core      configuration and cross-cutting concerns
    ├── models    workflow domain models
    ├── services  scan, workspace, clone, readiness, and patch orchestration
    ├── agents    Strands repository, interaction, readiness, and remediation agents
    └── tools     bounded repository, AI-flow, disclosure, and remediation context inspection
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
→ identify UI files associated with each confirmed interaction
→ search those files deterministically for rendered AI disclosure text
→ invoke the Article 50 Strands agent with bounded candidates and read-only tools
→ validate readiness outcomes and disclosure evidence
→ generate findings and map the aggregate readiness status
→ retain a bounded source snapshot for each remediable frontend finding
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

## Article 50 readiness boundary

The MVP evaluates only `ARTICLE_50_1_AI_INTERACTION_DISCLOSURE`. Its metadata and official source
reference are centralized in `app/core/article50_rules.py`. It does not attempt a general EU AI Act
assessment and does not automate the legal exception for cases where the AI nature may be obvious from
context.

`DisclosureInspector` starts from the Ticket 03 `frontend_entrypoint`, follows bounded relative UI
imports, identifies direct parent components, and extracts likely rendered text from JSX nodes,
user-visible attributes, rendered constants, and imported translation files. It never executes cloned
code. A README, source comment, backend log, dependency, or unrendered variable cannot become disclosure
evidence.

The Article 50 agent reasons over this deterministic shortlist. `TransparencyAssessmentValidator`
then establishes the final result: explicit and relevant UI evidence produces `PASS`; a complete
user-facing trace with no candidate produces `ACTION_REQUIRED`; incomplete, ambiguous, or dynamically
uncertain context produces `NEEDS_REVIEW`. Absence is explained from the inspected scope and complete
flow—it is never represented by fabricated source evidence.

## Remediation and human approval boundary

Ticket 05 operates only on an `ACTION_REQUIRED` finding for the primary Article 50 disclosure rule.
Before workspace cleanup, `ScanService` records the affected interaction, assessment, finding, verified
frontend source, and a SHA-256 digest in a process-local snapshot. The remediation agent later receives
only bounded excerpts of that snapshot through `get_remediation_context`; it has no shell, write, patch,
Git, or workspace tool.

The agent returns a structured `RemediationPlan`. `UnifiedDiffValidator` permits one existing file from
the captured context, rejects absolute paths, traversal, `.git`, binary patches, unknown files, empty or
oversized diffs, and dry-applies every hunk against the exact snapshot. It also reconstructs the proposed
source and uses the UI-text extractor to confirm that the added disclosure is explicit and likely
rendered—not merely a comment or unrendered variable.

`PatchService` stores validated proposals as `READY_FOR_REVIEW`. The API permits only
`READY_FOR_REVIEW → APPROVED` or `READY_FOR_REVIEW → REJECTED`; timestamps and an optional rejection
reason preserve the decision. No transition applies source changes. Patch application, rescanning, and
verification belong to Ticket 06.

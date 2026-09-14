# Amazon Bedrock live validation

Validation date: **2026-09-14**

This report records Tickets 09 and 10 without exposing AWS credentials, account identifiers,
credential paths, tokens, or model chain-of-thought.

## Configuration

```env
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-4-6
USE_MOCK_MODEL=false
```

The backend creates `boto3.Session` without embedded credentials, so Strands uses the standard AWS
credential provider chain. No application fallback changes a live failure into mock output.

## Final report

```text
BEDROCK LIVE: PASS

AI usage:                  1
AI interactions:           1
Article 50 assessments:    1
Findings:                   1

Initial readiness:         ACTION_REQUIRED
Patch generation:          READY_FOR_REVIEW
Approval:                  APPROVED
Application:               VERIFIED
Verification:              PASSED
Final readiness:           PASS
```

The application status advances to `VERIFIED` after the approved patch is applied and its re-scan
passes. The verification result separately reports `PASSED` and `disclosure_detected=true`.

## Safe interaction trace

```text
user_facing:       true
frontend file:     frontend/src/components/Chat.tsx
frontend evidence: const response = await fetch("/api/chat", {
API route:         POST /api/chat
backend handler:   backend/app/api/chat.py
AI provider:       Amazon Bedrock
confidence:        0.99
evidence types:    AI_USAGE, API_ROUTE, BACKEND_HANDLER, MODEL_CALL,
                   MODEL_CONFIGURATION, USER_INTERACTION
```

The controlled UI contains no explicit disclosure before remediation. README text, comments,
backend strings, logs, dependencies, and internal documentation are excluded from disclosure
detection. The resulting assessment is evidence-based:

```text
rule:                    ARTICLE_50_1_AI_INTERACTION_DISCLOSURE
status:                  ACTION_REQUIRED
disclosure_detected:     false
severity:                MEDIUM
remediation_available:   true
affected file:           frontend/src/components/Chat.tsx
```

## Root cause

The live investigation model conservatively returned `user_facing=false`. The interaction validator
treated that model-proposed boolean as a mandatory gate even though canonical repository evidence
proved the complete React caller → API route → backend handler → Bedrock invocation path. The Article
50 agent therefore filtered out the interaction and returned zero assessments and zero findings.

The validated evidence also lacked one model-proposed intermediate handler line. The previous
backend-to-model linkage check did not reconstruct that link from the source, so the interaction could
remain unconfirmed despite an exact route and model call.

## Fix implemented

- User-facing classification now derives from the exact validated UI → API → backend → model path;
  the model boolean is advisory and cannot veto stronger deterministic evidence.
- The validator reconstructs the backend link from the function containing the model invocation and
  the exact call to that function in the route handler.
- Background and model-only usage still fail the deterministic eligibility conditions and do not
  produce Article 50 interaction findings.
- Every eligible interaction is deterministically grounded to exactly one `PASS`, `ACTION_REQUIRED`,
  or `NEEDS_REVIEW` assessment, even if the agent omits it from an otherwise valid result.
- Article 50 structured output accepts model objects, mappings, and valid JSON serializations. Invalid
  output produces a controlled error and a safe log entry without logging model output.
- Unified diff validation can relocate a hunk only when its unchanged source context matches exactly
  once. This handled a live Bedrock hunk header that was one line off without weakening content,
  path, size, visibility, or approval checks.

## Tests

- Backend: **110 passed**.
- Backend Ruff: passed.
- Frontend Vitest: **8 passed**.
- Frontend ESLint: passed.
- Frontend TypeScript and production build: passed.
- Security controls: path traversal, repository isolation, approval boundary, replay protection,
  mutation boundary, patch size, source snapshot, rollback, exact diff-context matching, and secret
  scanning passed.
- Tracked-file secret scan found no AWS access key, secret access key, or session token.

## Known limitations

- User-facing classification requires a statically provable frontend endpoint caller, matching API
  route, backend handler, model invocation, and sufficient evidence confidence. Highly dynamic routing
  may remain non-user-facing or require manual investigation.
- Ambiguous disclosure wording, dynamic UI text, and translation-file candidates remain
  `NEEDS_REVIEW` by design.
- Live results depend on AWS credentials, Bedrock availability, model access, latency, and cost.
- The tool provides readiness assistance and evidence, not legal advice or compliance certification.

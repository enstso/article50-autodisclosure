# Demo video script

Target duration: **4:00–4:30**. Hard limit: stay below five minutes.

The recording should use **Try Demo Repository** unless live Bedrock has been validated immediately
before recording. The UI identifies demo mode, so describe it honestly as a deterministic presentation
fixture exercising the real workflow and safety services.

## Before recording

- [ ] Close irrelevant browser tabs and applications.
- [ ] Disable desktop and phone notifications.
- [ ] Hide personal email addresses, AWS account identifiers, support cases, and local private paths.
- [ ] Confirm no terminal, browser autofill, or frame can expose credentials or tokens.
- [ ] Use a readable browser zoom and a 1080p recording canvas when possible.
- [ ] Prepare the public repository URL for the closing frame.
- [ ] Reset the demo and verify backend/frontend status.
- [ ] Confirm the page clearly identifies demo mode, or clearly identify a validated live Bedrock run.
- [ ] Rehearse once and confirm the complete `ACTION REQUIRED → PASS` path.
- [ ] Start a timer and keep the final recording under five minutes.

Never show AWS access keys, session tokens, unnecessary account identifiers, personal emails, private
filesystem paths, support-case details, or terminal output containing secrets.

## 0:00–0:20 — Problem and pitch

**Screen:** Landing page and product statement.

**Narration:**

> AI is increasingly embedded into software, but a team can ship a user-facing AI feature without
> clearly telling people that they are interacting with AI. Article 50 AutoDisclosure is an autonomous
> software engineering agent that catches this before release.

Select **Try Demo Repository**. Briefly point out that the fixture gives a repeatable presentation of the
real scan, patch, and verification pipeline with deterministic model responses.

## 0:20–0:45 — Architecture

**Screen:** Keep the landing workflow visible, or briefly show the README architecture diagram.

**Narration:**

> A React interface calls a FastAPI backend. Strands reasoning stages use Amazon Bedrock for repository
> investigation, interaction reconstruction, transparency analysis, and remediation planning. The model
> receives bounded read-only tools; deterministic services validate evidence and control every source
> mutation.

Emphasize that Strands reasoning and deterministic safety controls have different responsibilities.

## 0:45–1:35 — Analyze the repository

**Screen:** Select **Analyze Repository** and let the result load.

**Narration while the timeline progresses:**

> The system creates an isolated workspace, analyzes the architecture, detects AI provider signals, and
> traces the feature from the user interface to the model invocation. It never installs dependencies or
> executes code from the analyzed repository.

When the result appears, pause on **ACTION REQUIRED**.

> The initial readiness result is Action Required: a direct user-facing AI interaction exists, but the
> relevant interface has no explicit AI disclosure.

Expected visible state: `ACTION REQUIRED`, one open Article 50 finding, one confirmed user-facing AI
interaction, and a demo-mode label.

## 1:35–2:15 — Interaction reconstruction and evidence

**Screen:** Show the interaction flow and expand or scroll through its evidence.

**Narration:**

> The agent did not stop at detecting an AI dependency. It reconstructed the complete user-facing path
> from this React chat component, through the FastAPI endpoint and backend service, to Amazon Bedrock.
> Each file, line, and snippet shown here was revalidated against the repository source.

Point out the React entrypoint, `POST /api/chat`, FastAPI handler, Bedrock invocation, missing-disclosure
explanation, and confidence.

## 2:15–2:55 — Generate and inspect remediation

**Screen:** Select **Generate Fix**, wait for the patch review, and show the exact unified diff.

**Narration:**

> Instead of stopping at a finding, the agent generates a minimal remediation. The proposed change adds
> one explicit notice to the same chat interface. The diff is dry-applied and checked for safe paths,
> scope, size, current source, and rendered disclosure text.

> No repository code has changed yet.

Pause long enough for the viewer to read: “You are chatting with an AI assistant.”

## 2:55–3:25 — Human approval

**Screen:** Show the approval controls, select **Approve**, and pause on the approved state.

**Narration:**

> The developer must review and explicitly approve the exact diff. Approval only records the decision;
> it still does not write source code. Application is a separate action.

Select **Apply & Verify**.

## 3:25–4:00 — Apply, re-scan, and verify

**Screen:** Let the activity timeline advance, then show the verification card.

**Narration:**

> The system revalidates the patch, snapshots the affected file, applies the approved change inside the
> isolated workspace, checks for unexpected mutations, and re-analyzes the affected interaction.

> The disclosure is now detected, the finding is resolved, and readiness moves from Action Required to
> Pass.

Expected visible state: patch `VERIFIED`, verification `PASSED`, `ACTION REQUIRED → PASS`, disclosure
evidence, and a coherent timeline ending in successful verification.

## 4:00–4:20 — Close

**Screen:** PASS result, then optionally the architecture diagram or repository README.

**Narration:**

> Article 50 AutoDisclosure turns AI transparency from a manual release checklist into an agentic
> software engineering workflow: detect, explain, remediate, approve, and verify. It combines the
> Strands Agents SDK, Amazon Bedrock, and a human-in-the-loop safety boundary so the agent can act without
> silently changing code.

End on the project name, public repository, and **Professional Agents** track.

## Reset between takes

1. Select **New Analysis**.
2. Select **Try Demo Repository**.
3. Select **Analyze Repository**.

Each demo scan uses a new ID and a fresh isolated copy of the original fixture. The previous patch never
modifies `backend/app/demo_repository`, so no manual repair is required.

## Fallbacks

- If live Bedrock access is unavailable, use the clearly labeled demo repository and do not imply that
  the recorded run called AWS.
- If the API disconnected, stop the take, restart the backend, and wait for **API Connected**.
- If a prior result cannot be restored after an API restart, begin a new demo scan; runtime records are
  intentionally process-local in this release.

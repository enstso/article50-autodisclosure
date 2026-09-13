# Devpost submission draft

## Project title

Article 50 AutoDisclosure

## Tagline

**Your AI feature shouldn't reach users without telling them it's AI.**

Secondary description: An autonomous AI transparency remediation agent for software teams.

## Intended track

Professional Agents

## Inspiration

AI functionality is increasingly added deep inside modern applications. A chatbot or assistant may span
a React component, an API route, a backend service, and a model provider. Traditional dependency scanning
can reveal that an AI SDK exists, but not necessarily whether a person directly interacts with the model
or whether the relevant interface clearly communicates that fact.

We wanted an agent that could understand this application flow and then act on the result without taking
source control away from the developer.

## What it does

Article 50 AutoDisclosure analyzes a public GitHub repository before release. It detects AI usage,
reconstructs user-facing interactions from the frontend to the provider, inspects the relevant interface
for an explicit AI disclosure, and creates an evidence-backed EU AI Act Article 50 readiness assessment.

When a confirmed interaction lacks a disclosure, the system can generate a minimal patch. The developer
reviews the exact diff and must explicitly approve it. A separate action applies the approved change in
the isolated workspace. The system then re-scans the affected interaction and verifies whether readiness
moved from `ACTION REQUIRED` to `PASS`.

This is more than dependency detection:

```text
AI signal → application-flow reconstruction → user-facing interaction
→ evidence-backed transparency analysis → remediation → human approval
→ bounded code change → verification
```

## How we built it

The user experience is a React and TypeScript application built with Vite and Tailwind CSS. A FastAPI
backend owns repository workspaces, scan state, evidence validation, remediation lifecycle, patch
application, and verification.

The Strands Agents SDK provides structured reasoning stages for repository investigation, AI interaction
reconstruction, Article 50 analysis, and remediation planning. Amazon Bedrock supplies the foundation
model for live scans, configured by default with the Claude Sonnet 4.6 global inference profile.

The key architectural choice is combining **agent reasoning with deterministic controls**. The agent
receives bounded, read-only repository tools and returns typed Pydantic proposals. Python services then
revalidate source evidence, enforce flow completeness, parse and dry-apply diffs, constrain paths and
patch size, require human approval, create a snapshot, detect unexpected mutations, roll back failures,
and verify the result. The agent never receives a shell or an arbitrary source-write tool.

For a reliable presentation, the application also includes a controlled React/FastAPI AI-chat fixture.
It uses deterministic model responses while still exercising the real scan, proposal, approval,
application, safety, and verification services.

## Challenges we ran into

### Reconstructing a real user-facing path

Finding an AI package is easy; proving that a person directly interacts with it is not. We required
evidence across the client caller, API route, backend handler or service link, and model invocation before
confirming an interaction.

### Separating source facts from model reasoning

A model can propose useful conclusions, but line references and snippets must be verifiable. We built an
evidence boundary that reopens every proposed source location and replaces it with canonical repository
content. Unsupported evidence is dropped.

### Assessing whether disclosure is actually visible

An AI-related string in a README, comment, log, or unrendered variable should not create a pass. The
disclosure inspector starts from the confirmed UI entrypoint and searches bounded rendered text,
user-visible attributes, related components, and translations.

### Allowing remediation without unsafe autonomous writes

Patch generation is useful only if it can be controlled. We split proposal, approval, and application
into separate states and surrounded application with allowlists, dry application, source-integrity
checks, snapshots, a repository-wide mutation manifest, rollback, and duplicate-application protection.

### Verifying without executing untrusted code

The scanner never installs dependencies or runs cloned code. Verification reuses the targeted static
Article 50 analysis for the affected interaction and requires validated disclosure evidence before
reporting `PASS`.

## Accomplishments that we're proud of

- An end-to-end `ACTION REQUIRED → remediation → approval → PASS` workflow.
- Cross-file reconstruction of a user-facing AI interaction, not just dependency detection.
- Evidence-backed findings with canonical files, lines, snippets, confidence, and explanations.
- Minimal, reviewable remediation proposals with a clear human approval boundary.
- Safe patch application with snapshots, unexpected-mutation detection, rollback, and replay protection.
- Automatic post-change verification without executing untrusted repository code.
- A controlled demo fixture that can be reset for repeatable sub-five-minute recordings.

## What we learned

Agents are most useful when interpretation is paired with narrow deterministic tools. Readiness analysis
requires understanding application flow, not merely matching package names. Human approval is valuable
for high-impact source changes, and verification is as important as generation: a proposed fix is not a
successful result until the relevant interaction is analyzed again.

## What's next

Future work could extend the same safety model to additional Article 50 transparency scenarios,
AI-generated content labeling, more frameworks and languages, authenticated private repository access,
a GitHub pull-request workflow, and a CI/CD release gate. Persistent workflow storage and an AgentCore
production deployment are also natural next steps after the hackathon MVP.

These are future directions, not features claimed by the current submission.

## Built with

- Amazon Bedrock
- Strands Agents SDK
- Python
- FastAPI
- Pydantic
- React
- TypeScript
- Vite
- Tailwind CSS
- Git and GitPython

## Scope note

Article 50 AutoDisclosure focuses on developer readiness for direct, user-facing AI interaction
disclosures under Article 50(1). It does not provide legal advice, certify compliance, guarantee
compliance, or confirm a legal violation.

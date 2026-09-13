# Hackathon submission checklist

Intended track: **Professional Agents**.

## Repository and release package

- [x] Repository name and documentation consistently use `article50-autodisclosure`.
- [x] Source code and controlled demo fixture are present.
- [x] MIT open-source license is present.
- [x] Root `.gitignore` excludes local environments, credentials, build output, and workspaces.
- [x] `.env` files are not tracked; example files contain no credentials.
- [x] README explains the problem, workflow, architecture, setup, AWS, Strands, security, and limitations.
- [x] Detailed Mermaid architecture diagram exists.
- [x] Strands responsibilities and deterministic safety controls are distinguished.
- [x] Amazon Bedrock and the configured model are documented.
- [x] Human approval and the separate apply boundary are documented.
- [x] Article 50 scope and non-legal-advice limitation are explicit.
- [x] Demo script and Devpost draft are complete.
- [x] Screenshot names and capture instructions are prepared.
- [ ] Review the final Git diff and commit Ticket 08.
- [ ] Push the approved commit to the public repository.

## Technical validation

- [x] Backend full test suite passes: 102 tests on 2026-09-13.
- [x] Backend Ruff check and `pip check` pass.
- [x] Security regression tests pass: traversal, isolation, approval, replay, mutation boundary, size,
      snapshot, and rollback.
- [x] Frontend Vitest suite passes: 8 tests on 2026-09-13.
- [x] Frontend ESLint check passes.
- [x] Frontend production build and TypeScript checks pass.
- [x] Backend starts using the documented command.
- [x] `/api/health` returns `ok` and `/docs` is accessible.
- [x] Controlled demo starts at `ACTION REQUIRED`.
- [x] Finding reports a missing AI interaction disclosure.
- [x] Patch adds an explicit disclosure and requires approval.
- [x] Approved patch applies and verifies as `PASS`.
- [x] Demo can be reset and repeated without manual fixture repair.
- [x] Browser console has no release-blocking error during the demo.
- [x] Live Bedrock was attempted on 2026-09-13; the configured model was unavailable and the pending
      external validation is disclosed in the README.

## Screenshots

- [ ] `01-landing.png`
- [ ] `02-action-required.png`
- [ ] `03-ai-interaction.png`
- [ ] `04-patch-review.png`
- [ ] `05-human-approval.png`
- [ ] `06-verification-pass.png`
- [ ] Confirm every screenshot hides credentials, personal information, and private paths.

## Demo video

- [ ] Close irrelevant browser tabs and disable notifications.
- [ ] Hide AWS keys, account identifiers, personal emails, private paths, and support details.
- [ ] Use readable zoom and 1080p capture where possible.
- [ ] Reset the demo before recording.
- [ ] Confirm backend, frontend, and intended model mode before recording.
- [ ] Record the complete `ACTION REQUIRED → PASS` workflow.
- [ ] Mention Strands Agents SDK, Amazon Bedrock, and human-in-the-loop safety.
- [ ] Keep the final edit below five minutes.
- [ ] Review audio, text readability, and secret safety frame by frame.
- [ ] Upload the video as public or unlisted according to hackathon rules.

## Devpost and final human review

- [ ] Complete the Devpost fields from `docs/devpost-submission.md`.
- [ ] Add the public repository URL.
- [ ] Add the final demo video URL.
- [ ] Add approved screenshots.
- [ ] Select the **Professional Agents** track.
- [ ] Verify the current AWS Builder ID and hackathon eligibility requirements.
- [ ] Confirm every claim matches the shipped implementation.
- [ ] Confirm live AWS validation wording is accurate.
- [ ] Review spelling, links, repository visibility, and video permissions.
- [ ] Submit before the official deadline.

Nothing in this checklist publishes, uploads, or submits the project automatically.

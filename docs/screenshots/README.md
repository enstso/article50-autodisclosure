# Screenshot capture guide

This directory intentionally contains instructions rather than fabricated product images. Capture the
final PNG files from the running application after the release candidate has passed all tests.

Use a consistent 16:9 browser viewport, readable zoom, and the same demo run where practical. Crop out
browser chrome only if the hackathon rules allow it. Do not show credentials, personal email addresses,
AWS account identifiers, private filesystem paths, support-case details, notifications, or unrelated
tabs.

## Required files

### `01-landing.png`

Capture the landing page with the product statement, **API Connected**, repository input,
**Try Demo Repository**, and Strands + Amazon Bedrock architecture strip visible.

### `02-action-required.png`

Run the controlled demo and capture `ACTION REQUIRED`, one open Article 50 finding, the repository name,
and demo-mode label before generating remediation.

### `03-ai-interaction.png`

Capture the reconstructed path `React Chat UI → POST /api/chat → FastAPI → Amazon Bedrock`. Include at
least one readable file-and-line evidence item.

### `04-patch-review.png`

Select **Generate Fix** and capture the remediation title, exact unified diff, added text “You are
chatting with an AI assistant.”, and approval/rejection actions.

### `05-human-approval.png`

Approve but do not apply. Capture status `APPROVED`, the unchanged diff, separate **Apply & Verify**
action, and language showing that approval alone does not mutate source.

### `06-verification-pass.png`

Apply the approved patch and capture overall `PASS`, patch status `VERIFIED`, verification `PASSED`, the
`ACTION REQUIRED → PASS` transition, and detected disclosure evidence or final timeline entry.

## Capture quality check

- [ ] Exact filenames are used.
- [ ] Text remains readable at the uploaded image size.
- [ ] Status badges and primary evidence are not cut off.
- [ ] All six images use consistent zoom and framing.
- [ ] No secret, credential, account identifier, email, private path, or notification is visible.
- [ ] Demo-mode screenshots are not described as live Bedrock calls.
- [ ] Images are reviewed before committing or uploading.

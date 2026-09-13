from hashlib import sha256
from pathlib import Path

import pytest

from app.core.article50_rules import ARTICLE_50_1_AI_INTERACTION_DISCLOSURE
from app.core.config import Settings
from app.core.exceptions import (
    FindingNotFoundError,
    FindingNotRemediableError,
    InvalidPatchError,
    InvalidPatchTransitionError,
    PatchTooLargeError,
    RemediationAgentError,
)
from app.models import (
    AIInteractionFlow,
    Evidence,
    EvidenceType,
    Finding,
    PatchStatus,
    ReadinessStatus,
    RemediationContext,
    RemediationPlan,
    SourceSnapshot,
    TransparencyAssessment,
)
from app.services.patch_service import PatchService, UnifiedDiffValidator

FIXTURE_FILE = (
    Path(__file__).parent / "fixtures" / "ai_chat_app" / "frontend" / "src" / "Chat.tsx"
)
TARGET_FILE = "frontend/src/Chat.tsx"
VALID_DIFF = """--- a/frontend/src/Chat.tsx
+++ b/frontend/src/Chat.tsx
@@ -15,6 +15,7 @@
   return (
     <form onSubmit={sendMessage}>
+      <p>You are chatting with an AI assistant.</p>
       <input value={message} onChange={(event) => setMessage(event.target.value)} />
       <button type="submit">Send</button>
     </form>
   );
"""


class FakeGenerator:
    def __init__(self, plan: RemediationPlan | None = None) -> None:
        self.plan = plan or _plan()

    def propose(self, context: RemediationContext) -> RemediationPlan:
        return self.plan


class FakeContextProvider:
    def __init__(self, context: RemediationContext | None) -> None:
        self.context = context
        self.events: list[str] = []
        self.patch_id: str | None = None

    def get_finding(self, finding_id: str):
        if self.context is None or finding_id != self.context.finding.id:
            return None
        return self.context.scan_id, self.context.finding.model_copy(deep=True)

    def get_remediation_context(self, finding_id: str):
        if self.context is None or finding_id != self.context.finding.id:
            return None
        return self.context.model_copy(deep=True)

    def link_patch_proposal(self, finding_id: str, patch_id: str) -> None:
        self.patch_id = patch_id

    def append_event(self, scan_id: str, event: str) -> None:
        self.events.append(event)


def _context(status: ReadinessStatus = ReadinessStatus.ACTION_REQUIRED) -> RemediationContext:
    content = FIXTURE_FILE.read_text(encoding="utf-8")
    interaction = AIInteractionFlow(
        id="interaction-1",
        name="Customer Support Chatbot",
        user_facing=True,
        frontend_entrypoint=TARGET_FILE,
        api_endpoint="POST /api/chat",
        backend_handler="backend/app/api/chat.py",
        ai_provider="Amazon Bedrock",
        flow_summary="The chat interface invokes Amazon Bedrock through the backend API.",
        evidence=[
            Evidence(
                file=TARGET_FILE,
                line=7,
                snippet='const response = await fetch("/api/chat", {',
                type=EvidenceType.USER_INTERACTION,
            )
        ],
        confidence=0.93,
    )
    finding = Finding(
        id="finding-1",
        rule=ARTICLE_50_1_AI_INTERACTION_DISCLOSURE,
        severity="MEDIUM",
        title="Missing AI interaction disclosure",
        explanation="No relevant disclosure was found.",
        affected_files=[TARGET_FILE],
        evidence=interaction.evidence,
        confidence=0.93,
        status=status,
        remediation_available=status == ReadinessStatus.ACTION_REQUIRED,
    )
    assessment = TransparencyAssessment(
        interaction_id=interaction.id,
        rule_id=ARTICLE_50_1_AI_INTERACTION_DISCLOSURE,
        status=status,
        disclosure_detected=False if status == ReadinessStatus.ACTION_REQUIRED else None,
        explanation="Evidence-backed assessment.",
        evidence=interaction.evidence,
        inspected_files=[TARGET_FILE],
        confidence=0.93,
    )
    return RemediationContext(
        scan_id="00000000-0000-0000-0000-000000000001",
        finding=finding,
        assessment=assessment,
        interaction=interaction,
        source_files=[
            SourceSnapshot(
                file=TARGET_FILE,
                content=content,
                sha256=sha256(content.encode("utf-8")).hexdigest(),
            )
        ],
    )


def _plan(diff: str = VALID_DIFF) -> RemediationPlan:
    return RemediationPlan(
        title="Add AI disclosure to customer support chat",
        rationale="Adds a clear notice inside the existing chat form.",
        disclosure_text="You are chatting with an AI assistant.",
        affected_files=[TARGET_FILE],
        unified_diff=diff,
        confidence=0.94,
    )


def test_action_required_generates_reviewable_patch_without_mutating_source() -> None:
    context = _context()
    provider = FakeContextProvider(context)
    before = sha256(FIXTURE_FILE.read_bytes()).hexdigest()
    service = PatchService(remediation_factory=FakeGenerator)

    proposal = service.generate(context.finding.id, provider)
    approved = service.approve(proposal.id, provider)
    after = sha256(FIXTURE_FILE.read_bytes()).hexdigest()

    assert proposal.status == PatchStatus.READY_FOR_REVIEW
    assert proposal.affected_files == [TARGET_FILE]
    assert proposal.disclosure_text == "You are chatting with an AI assistant."
    assert proposal.unified_diff == VALID_DIFF
    assert proposal.original_snippets
    assert proposal.proposed_snippets
    assert approved.status == PatchStatus.APPROVED
    assert approved.approved_at is not None
    assert before == after
    assert provider.patch_id == proposal.id
    assert provider.events[-1] == "Patch approved"


def test_ready_patch_can_be_rejected_once_with_optional_reason() -> None:
    context = _context()
    provider = FakeContextProvider(context)
    service = PatchService(remediation_factory=FakeGenerator)
    proposal = service.generate(context.finding.id, provider)

    rejected = service.reject(proposal.id, provider, "Please change the wording.")

    assert rejected.status == PatchStatus.REJECTED
    assert rejected.rejected_at is not None
    assert rejected.rejection_reason == "Please change the wording."
    with pytest.raises(InvalidPatchTransitionError):
        service.approve(proposal.id, provider)


@pytest.mark.parametrize(
    "status",
    [ReadinessStatus.PASS, ReadinessStatus.NEEDS_REVIEW],
)
def test_non_action_required_findings_are_not_remediable(status: ReadinessStatus) -> None:
    context = _context(status)
    provider = FakeContextProvider(context)

    with pytest.raises(FindingNotRemediableError):
        PatchService(remediation_factory=FakeGenerator).generate(context.finding.id, provider)


def test_unknown_finding_is_controlled() -> None:
    with pytest.raises(FindingNotFoundError):
        PatchService(remediation_factory=FakeGenerator).generate(
            "unknown", FakeContextProvider(None)
        )


def test_invalid_structured_remediation_output_is_controlled() -> None:
    class InvalidGenerator:
        def propose(self, context):
            return {"title": "Incomplete"}

    context = _context()
    with pytest.raises(RemediationAgentError):
        PatchService(remediation_factory=InvalidGenerator).generate(
            context.finding.id, FakeContextProvider(context)
        )


@pytest.mark.parametrize(
    "path",
    [
        "../../etc/passwd",
        "/etc/passwd",
        r"C:\Windows\system.ini",
        ".git/config",
        "frontend/src/Unknown.tsx",
    ],
)
def test_diff_validator_rejects_unsafe_and_unknown_paths(path: str) -> None:
    diff = VALID_DIFF.replace("frontend/src/Chat.tsx", path)
    plan = _plan(diff).model_copy(update={"affected_files": [path]})

    with pytest.raises(InvalidPatchError):
        UnifiedDiffValidator().validate(plan, _context())


@pytest.mark.parametrize(
    "unsafe_diff",
    [
        "GIT binary patch\nliteral 1\nA",
        VALID_DIFF.replace("   return (", "   return somethingElse("),
        VALID_DIFF.replace(
            "+      <p>You are chatting with an AI assistant.</p>",
            "+      <p>Smart assistant</p>",
        ),
        VALID_DIFF.replace(
            "+      <p>You are chatting with an AI assistant.</p>",
            "+      {/* You are chatting with an AI assistant. */}",
        ),
    ],
)
def test_diff_validator_rejects_binary_mismatched_and_vague_patches(
    unsafe_diff: str,
) -> None:
    with pytest.raises(InvalidPatchError):
        UnifiedDiffValidator().validate(_plan(unsafe_diff), _context())


def test_diff_validator_rejects_oversized_patch() -> None:
    validator = UnifiedDiffValidator(Settings(max_patch_lines=5))

    with pytest.raises(PatchTooLargeError):
        validator.validate(_plan(), _context())


def test_diff_validator_rejects_tampered_source_snapshot() -> None:
    context = _context()
    context.source_files[0].content += "\n// changed after snapshot"

    with pytest.raises(InvalidPatchError, match="integrity"):
        UnifiedDiffValidator().validate(_plan(), context)

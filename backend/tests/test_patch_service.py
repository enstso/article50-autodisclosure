import shutil
from datetime import UTC, datetime
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
    PatchAlreadyAppliedError,
    PatchApplicationError,
    PatchNotApprovedError,
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
    VerificationResult,
    VerificationStatus,
)
from app.services.patch_service import PatchService, UnifiedDiffValidator
from app.services.workspace_service import WorkspaceService

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


class FakeVerificationProvider(FakeContextProvider):
    def __init__(
        self,
        context: RemediationContext,
        status: VerificationStatus = VerificationStatus.PASSED,
    ) -> None:
        super().__init__(context)
        self.verification_status = status

    def verify_patch(self, proposal) -> VerificationResult:
        if self.verification_status == VerificationStatus.PASSED:
            new_status = ReadinessStatus.PASS
            detected = True
        elif self.verification_status == VerificationStatus.NEEDS_REVIEW:
            new_status = ReadinessStatus.NEEDS_REVIEW
            detected = None
        else:
            new_status = ReadinessStatus.ACTION_REQUIRED
            detected = False
        return VerificationResult(
            id="00000000-0000-0000-0000-000000000099",
            patch_id=proposal.id,
            scan_id=proposal.scan_id,
            finding_id=proposal.finding_id,
            status=self.verification_status,
            previous_readiness_status=ReadinessStatus.ACTION_REQUIRED,
            new_readiness_status=new_status,
            disclosure_detected=detected,
            explanation="Controlled verification result.",
            evidence=proposal.proposed_snippets if detected else [],
            verified_at=datetime.now(UTC),
        )


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
    assert provider.events[-1] == "Human approved remediation"


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


def _approved_application(
    tmp_path: Path,
    verification_status: VerificationStatus = VerificationStatus.PASSED,
) -> tuple[PatchService, FakeVerificationProvider, str, WorkspaceService]:
    settings = Settings(workspace_path=tmp_path)
    workspace = WorkspaceService(settings)
    context = _context()
    workspace.create_workspace(context.scan_id)
    shutil.copytree(
        Path(__file__).parent / "fixtures" / "ai_chat_app",
        workspace.get_repository_path(context.scan_id),
    )
    provider = FakeVerificationProvider(context, verification_status)
    service = PatchService(
        settings=settings,
        remediation_factory=FakeGenerator,
        workspace_service=workspace,
    )
    proposal = service.generate(context.finding.id, provider)
    service.approve(proposal.id, provider)
    return service, provider, proposal.id, workspace


def test_approved_patch_is_snapshotted_applied_and_verified(tmp_path: Path) -> None:
    service, provider, patch_id, workspace = _approved_application(tmp_path)
    repository_file = workspace.get_repository_path(provider.context.scan_id) / TARGET_FILE
    original = repository_file.read_text(encoding="utf-8")

    response = service.apply(patch_id, provider)

    assert response.patch_status == PatchStatus.VERIFIED
    assert response.verification.status == VerificationStatus.PASSED
    assert "You are chatting with an AI assistant." in repository_file.read_text(
        encoding="utf-8"
    )
    snapshot = workspace.get_snapshot_path(provider.context.scan_id, patch_id) / TARGET_FILE
    assert snapshot.read_text(encoding="utf-8") == original
    assert [
        path.relative_to(snapshot.parents[2]).as_posix()
        for path in snapshot.parents[2].rglob("*")
        if path.is_file()
    ] == [TARGET_FILE]
    stored = service.get(patch_id)
    assert stored.applied_at is not None
    assert stored.verified_at is not None
    assert stored.modified_files == [TARGET_FILE]
    assert service.get_verification(response.verification.id) == response.verification
    assert provider.events[-5:] == [
        "Validating patch",
        "Creating safety snapshot",
        "Applying patch",
        "Patch applied successfully",
        "Re-scanning affected interaction",
    ]


@pytest.mark.parametrize("decision", ["ready", "rejected"])
def test_non_approved_patch_cannot_be_applied(tmp_path: Path, decision: str) -> None:
    settings = Settings(workspace_path=tmp_path)
    workspace = WorkspaceService(settings)
    context = _context()
    workspace.create_workspace(context.scan_id)
    shutil.copytree(
        Path(__file__).parent / "fixtures" / "ai_chat_app",
        workspace.get_repository_path(context.scan_id),
    )
    provider = FakeVerificationProvider(context)
    service = PatchService(
        settings=settings,
        remediation_factory=FakeGenerator,
        workspace_service=workspace,
    )
    proposal = service.generate(context.finding.id, provider)
    if decision == "rejected":
        service.reject(proposal.id, provider)

    with pytest.raises(PatchNotApprovedError):
        service.apply(proposal.id, provider)


def test_verified_patch_cannot_be_applied_twice(tmp_path: Path) -> None:
    service, provider, patch_id, _ = _approved_application(tmp_path)
    service.apply(patch_id, provider)

    with pytest.raises(PatchAlreadyAppliedError):
        service.apply(patch_id, provider)


@pytest.mark.parametrize(
    "unsafe_diff,affected_files",
    [
        (
            VALID_DIFF.replace("frontend/src/Chat.tsx", "../../etc/passwd"),
            ["../../etc/passwd"],
        ),
        (
            VALID_DIFF
            + "\n--- a/backend/app/main.py\n+++ b/backend/app/main.py\n"
            + "@@ -1,1 +1,1 @@\n-old\n+new\n",
            [TARGET_FILE],
        ),
    ],
)
def test_application_revalidates_paths_and_affected_file_boundary(
    tmp_path: Path, unsafe_diff: str, affected_files: list[str]
) -> None:
    service, provider, patch_id, _ = _approved_application(tmp_path)
    approved = service.get(patch_id)
    service._patches[patch_id] = approved.model_copy(
        update={"unified_diff": unsafe_diff, "affected_files": affected_files}
    )

    with pytest.raises(InvalidPatchError):
        service.apply(patch_id, provider)

    assert service.get(patch_id).status == PatchStatus.FAILED


def test_failed_write_restores_snapshot_and_marks_patch_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import patch_service as patch_module

    service, provider, patch_id, workspace = _approved_application(tmp_path)
    target = workspace.get_repository_path(provider.context.scan_id) / TARGET_FILE
    original = target.read_bytes()

    def fail_after_write(path: Path, content: str) -> None:
        path.write_bytes(content.encode("utf-8"))
        raise OSError("controlled write failure")

    monkeypatch.setattr(patch_module, "_write_mutation_source", fail_after_write)

    with pytest.raises(PatchApplicationError):
        service.apply(patch_id, provider)

    assert target.read_bytes() == original
    assert service.get(patch_id).status == PatchStatus.FAILED
    assert "Rolling back changes" in provider.events


def test_failed_semantic_verification_keeps_patch_applied_and_action_required(
    tmp_path: Path,
) -> None:
    service, provider, patch_id, _ = _approved_application(
        tmp_path, VerificationStatus.FAILED
    )

    response = service.apply(patch_id, provider)

    assert response.patch_status == PatchStatus.APPLIED
    assert response.verification.status == VerificationStatus.FAILED
    assert response.verification.new_readiness_status == ReadinessStatus.ACTION_REQUIRED
    with pytest.raises(PatchAlreadyAppliedError):
        service.apply(patch_id, provider)


def test_patch_cannot_modify_another_scan_workspace(tmp_path: Path) -> None:
    service, provider, patch_id, workspace = _approved_application(tmp_path)
    second_scan_id = "00000000-0000-0000-0000-000000000002"
    workspace.create_workspace(second_scan_id)
    shutil.copytree(
        Path(__file__).parent / "fixtures" / "ai_chat_app",
        workspace.get_repository_path(second_scan_id),
    )
    second_target = workspace.get_repository_path(second_scan_id) / TARGET_FILE
    second_before = second_target.read_bytes()

    service.apply(patch_id, provider)

    assert second_target.read_bytes() == second_before

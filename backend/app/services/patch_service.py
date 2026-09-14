import os
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath, PureWindowsPath
from threading import Lock
from typing import Protocol
from uuid import uuid4

from pydantic import ValidationError

from app.agents import RemediationAgent
from app.core.article50_rules import ARTICLE_50_1_AI_INTERACTION_DISCLOSURE
from app.core.config import Settings, get_settings
from app.core.disclosure_detection_rules import is_explicit_ai_disclosure
from app.core.exceptions import (
    FindingNotFoundError,
    FindingNotRemediableError,
    InvalidPatchError,
    InvalidPatchTransitionError,
    PatchAlreadyAppliedError,
    PatchApplicationError,
    PatchNotApprovedError,
    PatchNotFoundError,
    PatchRollbackError,
    PatchTooLargeError,
    RemediationAgentError,
    RemediationContextError,
)
from app.demo import DemoRemediationGenerator
from app.models import (
    Evidence,
    EvidenceType,
    Finding,
    PatchApplyResponse,
    PatchProposal,
    PatchStatus,
    ReadinessStatus,
    RemediationContext,
    RemediationPlan,
    VerificationResult,
    VerificationStatus,
)
from app.services.workspace_service import WorkspaceService
from app.tools.disclosure_tools import extract_user_visible_strings

HUNK_HEADER_PATTERN = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? "
    r"\+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@(?: .*)?$"
)
MAX_CHANGED_LINES = 24


class RemediationGenerator(Protocol):
    def propose(self, context: RemediationContext) -> RemediationPlan: ...


class PatchContextProvider(Protocol):
    def get_finding(self, finding_id: str) -> tuple[str, Finding] | None: ...

    def get_remediation_context(self, finding_id: str) -> RemediationContext | None: ...

    def link_patch_proposal(self, finding_id: str, patch_id: str) -> None: ...

    def append_event(self, scan_id: str, event: str) -> None: ...

    def verify_patch(self, proposal: PatchProposal) -> VerificationResult: ...

    def is_demo_scan(self, scan_id: str) -> bool: ...


@dataclass(frozen=True)
class ValidatedDiff:
    affected_files: list[str]
    original_snippets: list[Evidence]
    proposed_snippets: list[Evidence]
    proposed_contents: dict[str, str]


class UnifiedDiffValidator:
    """Validate and dry-apply a one-file disclosure patch without touching disk."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def validate(
        self, plan: RemediationPlan, context: RemediationContext
    ) -> ValidatedDiff:
        diff = plan.unified_diff
        if not diff.strip():
            raise InvalidPatchError("The proposed diff is empty.")
        if "\x00" in diff or "GIT binary patch" in diff or "Binary files " in diff:
            raise InvalidPatchError("Binary patches are not allowed.")

        lines = diff.rstrip("\n").splitlines()
        if len(lines) > self.settings.max_patch_lines:
            raise PatchTooLargeError(
                f"The proposed diff exceeds the {self.settings.max_patch_lines}-line limit."
            )
        changed_lines = sum(
            line.startswith(("+", "-"))
            and not line.startswith(("+++ ", "--- "))
            for line in lines
        )
        if changed_lines > MAX_CHANGED_LINES:
            raise InvalidPatchError("The proposed diff changes too many lines for a minimal fix.")
        if len(lines) < 4 or not lines[0].startswith("--- ") or not lines[1].startswith("+++ "):
            raise InvalidPatchError("A plain unified diff with file headers is required.")
        if sum(line.startswith("--- ") for line in lines) != 1 or sum(
            line.startswith("+++ ") for line in lines
        ) != 1:
            raise InvalidPatchError("Ticket 05 proposals may modify exactly one file.")

        old_path = _validated_header_path(lines[0], "--- ")
        new_path = _validated_header_path(lines[1], "+++ ")
        if old_path != new_path:
            raise InvalidPatchError("Renames and file creation are not allowed.")

        sources = {source.file: source for source in context.source_files}
        if any(
            source.sha256 != sha256(source.content.encode("utf-8")).hexdigest()
            for source in sources.values()
        ):
            raise InvalidPatchError("The remediation source snapshot failed integrity validation.")
        allowed_files = set(sources)
        if old_path not in allowed_files:
            raise InvalidPatchError("The diff references a file outside the remediation context.")
        if len(plan.affected_files) != 1 or set(plan.affected_files) != {old_path}:
            raise InvalidPatchError("Affected files do not match the unified diff.")
        if not is_explicit_ai_disclosure(plan.disclosure_text):
            raise InvalidPatchError("The proposed disclosure does not explicitly identify AI.")

        original_snippets, added_lines, proposed_content = _dry_apply(
            lines[2:], old_path, sources[old_path].content
        )
        added_plain_text = re.sub(r"<[^>]+>", " ", " ".join(text for _, text in added_lines))
        normalized_added = " ".join(added_plain_text.split()).casefold()
        normalized_disclosure = " ".join(plan.disclosure_text.split()).casefold()
        if normalized_disclosure not in normalized_added:
            raise InvalidPatchError("The disclosure text is not present in added diff lines.")
        if not added_lines:
            raise InvalidPatchError("The proposed diff does not add source text.")
        added_line_numbers = {line for line, _ in added_lines}
        disclosure_strings = [
            item
            for item in extract_user_visible_strings(old_path, proposed_content)
            if item["line"] in added_line_numbers
            and normalized_disclosure in " ".join(item["text"].split()).casefold()
        ]
        if not disclosure_strings:
            raise InvalidPatchError(
                "The proposed disclosure is not rendered as user-visible UI text."
            )
        proposed_snippets = [
            Evidence(
                file=old_path,
                line=item["line"],
                snippet=item["snippet"],
                type=EvidenceType.DISCLOSURE,
            )
            for item in disclosure_strings
        ]

        return ValidatedDiff(
            affected_files=[old_path],
            original_snippets=original_snippets,
            proposed_snippets=proposed_snippets,
            proposed_contents={old_path: proposed_content},
        )


class PatchService:
    def __init__(
        self,
        settings: Settings | None = None,
        remediation_factory: Callable[[], RemediationGenerator] = RemediationAgent,
        validator: UnifiedDiffValidator | None = None,
        workspace_service: WorkspaceService | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.remediation_factory = remediation_factory
        self.validator = validator or UnifiedDiffValidator(self.settings)
        self.workspace_service = workspace_service or WorkspaceService(self.settings)
        self._patches: dict[str, PatchProposal] = {}
        self._verifications: dict[str, VerificationResult] = {}
        self._lock = Lock()
        self._application_lock = Lock()

    def generate(
        self, finding_id: str, context_provider: PatchContextProvider
    ) -> PatchProposal:
        finding_record = context_provider.get_finding(finding_id)
        if finding_record is None:
            raise FindingNotFoundError("Finding not found.")
        scan_id, finding = finding_record
        if (
            finding.status != ReadinessStatus.ACTION_REQUIRED
            or finding.rule != ARTICLE_50_1_AI_INTERACTION_DISCLOSURE
        ):
            raise FindingNotRemediableError(
                "Only ACTION_REQUIRED AI interaction disclosure findings are remediable."
            )
        context = context_provider.get_remediation_context(finding_id)
        if context is None or not finding.remediation_available:
            raise RemediationContextError(
                "No safe frontend remediation context is available for this finding."
            )

        context_provider.append_event(scan_id, "Generating remediation")
        context_provider.append_event(scan_id, "Inspecting affected UI component")
        context_provider.append_event(scan_id, "Preparing minimal patch")
        try:
            is_demo_scan = getattr(context_provider, "is_demo_scan", lambda _scan_id: False)
            generator = (
                DemoRemediationGenerator()
                if is_demo_scan(scan_id)
                else self.remediation_factory()
            )
            plan = RemediationPlan.model_validate(generator.propose(context))
        except ValidationError as error:
            raise RemediationAgentError(
                "The remediation agent returned an invalid structured result."
            ) from error
        context_provider.append_event(scan_id, "Validating proposed diff")
        validated = self.validator.validate(plan, context)

        proposal = PatchProposal(
            id=str(uuid4()),
            scan_id=scan_id,
            finding_id=finding_id,
            status=PatchStatus.READY_FOR_REVIEW,
            title=plan.title,
            rationale=plan.rationale,
            affected_files=validated.affected_files,
            disclosure_text=plan.disclosure_text,
            unified_diff=plan.unified_diff,
            original_snippets=validated.original_snippets,
            proposed_snippets=validated.proposed_snippets,
            confidence=plan.confidence,
            created_at=datetime.now(UTC),
        )
        with self._lock:
            self._patches[proposal.id] = proposal.model_copy(deep=True)
        context_provider.link_patch_proposal(finding_id, proposal.id)
        context_provider.append_event(scan_id, "Patch ready for review")
        context_provider.append_event(scan_id, "Waiting for human approval")
        return proposal.model_copy(deep=True)

    def get(self, patch_id: str) -> PatchProposal:
        with self._lock:
            proposal = self._patches.get(patch_id)
            if proposal is None:
                raise PatchNotFoundError("Patch proposal not found.")
            return proposal.model_copy(deep=True)

    def approve(
        self, patch_id: str, context_provider: PatchContextProvider
    ) -> PatchProposal:
        proposal = self._transition(patch_id, PatchStatus.APPROVED)
        context_provider.append_event(proposal.scan_id, "Human approved remediation")
        return proposal

    def reject(
        self,
        patch_id: str,
        context_provider: PatchContextProvider,
        reason: str | None = None,
    ) -> PatchProposal:
        proposal = self._transition(patch_id, PatchStatus.REJECTED, reason=reason)
        context_provider.append_event(proposal.scan_id, "Patch rejected")
        return proposal

    def apply(
        self, patch_id: str, context_provider: PatchContextProvider
    ) -> PatchApplyResponse:
        """Apply one approved diff inside its scan workspace and verify the outcome."""

        with self._application_lock:
            proposal = self.get(patch_id)
            if proposal.status in {PatchStatus.APPLIED, PatchStatus.VERIFIED}:
                raise PatchAlreadyAppliedError("Patch has already been applied.")
            if proposal.status != PatchStatus.APPROVED:
                raise PatchNotApprovedError("Only an approved patch can be applied.")

            context_provider.append_event(proposal.scan_id, "Validating patch")
            try:
                context = context_provider.get_remediation_context(proposal.finding_id)
                if context is None or context.scan_id != proposal.scan_id:
                    raise InvalidPatchError("The patch remediation context is unavailable.")
                plan = _proposal_plan(proposal)
                repository_root = self.workspace_service.get_repository_path(
                    proposal.scan_id
                ).resolve()
                paths = {
                    relative: _safe_mutation_path(repository_root, relative)
                    for relative in proposal.affected_files
                }
                live_sources = []
                original_sources = {source.file: source for source in context.source_files}
                for relative, path in paths.items():
                    if relative not in original_sources:
                        raise InvalidPatchError(
                            "The affected files do not match the approved remediation context."
                        )
                    content = _read_mutation_source(path, self.settings)
                    digest = sha256(content.encode("utf-8")).hexdigest()
                    if digest != original_sources[relative].sha256:
                        raise InvalidPatchError(
                            "The target source changed after the patch was proposed."
                        )
                    live_sources.append(
                        original_sources[relative].model_copy(
                            update={"content": content, "sha256": digest}
                        )
                    )
                live_context = context.model_copy(
                    update={"source_files": live_sources}, deep=True
                )
                validated = self.validator.validate(plan, live_context)
                if set(validated.affected_files) != set(proposal.affected_files):
                    raise InvalidPatchError(
                        "The unified diff references files outside the approved boundary."
                    )
            except Exception:
                self._set_application_status(patch_id, PatchStatus.FAILED)
                context_provider.append_event(proposal.scan_id, "Patch application failed")
                raise

            self._set_application_status(patch_id, PatchStatus.APPLYING)
            snapshot_root: Path | None = None
            mutation_started = False
            try:
                before_manifest = _repository_manifest(repository_root)
                context_provider.append_event(proposal.scan_id, "Creating safety snapshot")
                snapshot_root = self._create_snapshot(proposal, paths)
                context_provider.append_event(proposal.scan_id, "Applying patch")
                mutation_started = True
                for relative, path in paths.items():
                    _write_mutation_source(path, validated.proposed_contents[relative])

                after_manifest = _repository_manifest(repository_root)
                changed_files = _changed_files(before_manifest, after_manifest)
                expected_files = set(proposal.affected_files)
                if changed_files != expected_files:
                    raise PatchApplicationError(
                        "Patch application changed files outside the approved boundary."
                    )
            except Exception as error:
                if mutation_started and snapshot_root is not None:
                    context_provider.append_event(proposal.scan_id, "Rolling back changes")
                    try:
                        self._restore_snapshot(snapshot_root, paths)
                    except OSError as rollback_error:
                        self._set_application_status(patch_id, PatchStatus.FAILED)
                        raise PatchRollbackError(
                            "Patch application failed and rollback could not be completed."
                        ) from rollback_error
                self._set_application_status(patch_id, PatchStatus.FAILED)
                context_provider.append_event(proposal.scan_id, "Patch application failed")
                if isinstance(error, (InvalidPatchError, PatchApplicationError)):
                    raise
                raise PatchApplicationError("The approved patch could not be applied.") from error

            applied = self._set_application_status(
                patch_id,
                PatchStatus.APPLIED,
                applied_at=datetime.now(UTC),
                modified_files=sorted(proposal.affected_files),
            )
            context_provider.append_event(proposal.scan_id, "Patch applied successfully")
            context_provider.append_event(proposal.scan_id, "Re-scanning affected interaction")
            verification = context_provider.verify_patch(applied)
            with self._lock:
                self._verifications[verification.id] = verification.model_copy(deep=True)

            if verification.status == VerificationStatus.PASSED:
                updated = self._set_application_status(
                    patch_id,
                    PatchStatus.VERIFIED,
                    verified_at=verification.verified_at,
                )
            else:
                updated = self.get(patch_id)
            return PatchApplyResponse(
                patch_id=patch_id,
                patch_status=updated.status,
                verification=verification,
            )

    def get_verification(self, verification_id: str) -> VerificationResult | None:
        with self._lock:
            result = self._verifications.get(verification_id)
            return result.model_copy(deep=True) if result is not None else None

    def get_verification_for_patch(self, patch_id: str) -> VerificationResult | None:
        with self._lock:
            result = next(
                (
                    verification
                    for verification in self._verifications.values()
                    if verification.patch_id == patch_id
                ),
                None,
            )
            return result.model_copy(deep=True) if result is not None else None

    def _create_snapshot(
        self, proposal: PatchProposal, paths: dict[str, Path]
    ) -> Path:
        snapshot_root = self.workspace_service.get_snapshot_path(
            proposal.scan_id, proposal.id
        )
        snapshot_root.mkdir(parents=True, exist_ok=False)
        try:
            for relative, source in paths.items():
                destination = snapshot_root.joinpath(*PurePosixPath(relative).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        except OSError:
            shutil.rmtree(snapshot_root, ignore_errors=True)
            raise
        return snapshot_root

    @staticmethod
    def _restore_snapshot(snapshot_root: Path, paths: dict[str, Path]) -> None:
        for relative, destination in paths.items():
            source = snapshot_root.joinpath(*PurePosixPath(relative).parts)
            shutil.copy2(source, destination)

    def _set_application_status(
        self,
        patch_id: str,
        status: PatchStatus,
        **updates: object,
    ) -> PatchProposal:
        with self._lock:
            current = self._patches.get(patch_id)
            if current is None:
                raise PatchNotFoundError("Patch proposal not found.")
            updated = current.model_copy(
                update={"status": status, **updates}, deep=True
            )
            self._patches[patch_id] = updated
            return updated.model_copy(deep=True)

    def _transition(
        self,
        patch_id: str,
        status: PatchStatus,
        *,
        reason: str | None = None,
    ) -> PatchProposal:
        with self._lock:
            current = self._patches.get(patch_id)
            if current is None:
                raise PatchNotFoundError("Patch proposal not found.")
            if current.status != PatchStatus.READY_FOR_REVIEW:
                raise InvalidPatchTransitionError(
                    "Only a patch ready for review can be approved or rejected."
                )
            timestamp = datetime.now(UTC)
            updates: dict[str, object] = {"status": status}
            if status == PatchStatus.APPROVED:
                updates["approved_at"] = timestamp
            else:
                updates["rejected_at"] = timestamp
                updates["rejection_reason"] = reason.strip() if reason and reason.strip() else None
            updated = current.model_copy(update=updates, deep=True)
            self._patches[patch_id] = updated
            return updated.model_copy(deep=True)


def _validated_header_path(line: str, prefix: str) -> str:
    raw = line[len(prefix) :].split("\t", maxsplit=1)[0].strip()
    if raw in {"/dev/null", "dev/null"}:
        raise InvalidPatchError("File creation and deletion are not allowed.")
    if raw.startswith(("a/", "b/")):
        raw = raw[2:]
    windows = PureWindowsPath(raw)
    posix = PurePosixPath(raw.replace("\\", "/"))
    if (
        not raw
        or windows.is_absolute()
        or windows.drive
        or posix.is_absolute()
        or ".." in posix.parts
        or ".git" in {part.casefold() for part in posix.parts}
        or "\\" in raw
    ):
        raise InvalidPatchError("The proposed diff contains an unsafe path.")
    normalized = posix.as_posix()
    if normalized in {"", "."}:
        raise InvalidPatchError("The proposed diff contains an unsafe path.")
    return normalized


def _proposal_plan(proposal: PatchProposal) -> RemediationPlan:
    return RemediationPlan(
        title=proposal.title,
        rationale=proposal.rationale,
        disclosure_text=proposal.disclosure_text or "",
        affected_files=proposal.affected_files,
        unified_diff=proposal.unified_diff,
        confidence=proposal.confidence,
    )


def _safe_mutation_path(repository_root: Path, relative_path: str) -> Path:
    raw = relative_path.strip()
    windows = PureWindowsPath(raw)
    posix = PurePosixPath(raw.replace("\\", "/"))
    if (
        not raw
        or windows.is_absolute()
        or windows.drive
        or posix.is_absolute()
        or ".." in posix.parts
        or ".git" in {part.casefold() for part in posix.parts}
        or "\\" in raw
        or posix.as_posix() in {"", "."}
    ):
        raise InvalidPatchError("The patch target path is unsafe.")
    normalized = posix.as_posix()
    unresolved = repository_root.joinpath(*PurePosixPath(normalized).parts)
    current = unresolved
    while current != repository_root:
        if current.is_symlink():
            raise InvalidPatchError("Symbolic-link patch targets are not allowed.")
        current = current.parent
    candidate = unresolved.resolve()
    try:
        candidate.relative_to(repository_root)
    except ValueError as error:
        raise InvalidPatchError("The patch target is outside the repository workspace.") from error
    if not candidate.is_file():
        raise InvalidPatchError("The patch target must be an existing regular source file.")
    return candidate


def _read_mutation_source(path: Path, settings: Settings) -> str:
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise InvalidPatchError("The patch target could not be read.") from error
    if len(payload) > settings.max_file_size_kb * 1024:
        raise InvalidPatchError("The patch target exceeds the configured file size limit.")
    if b"\x00" in payload:
        raise InvalidPatchError("Binary patch targets are not allowed.")
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InvalidPatchError("Binary patch targets are not allowed.") from error


def _write_mutation_source(path: Path, content: str) -> None:
    try:
        path.write_bytes(content.encode("utf-8"))
    except OSError as error:
        raise PatchApplicationError("The approved patch could not be written.") from error


def _repository_manifest(repository_root: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for current, directory_names, file_names in os.walk(repository_root, followlinks=False):
        current_path = Path(current)
        directory_names[:] = sorted(
            name for name in directory_names if not (current_path / name).is_symlink()
        )
        for name in sorted(file_names):
            path = current_path / name
            relative = path.relative_to(repository_root).as_posix()
            if path.is_symlink():
                manifest[relative] = f"symlink:{os.readlink(path)}"
                continue
            try:
                manifest[relative] = sha256(path.read_bytes()).hexdigest()
            except OSError as error:
                raise PatchApplicationError(
                    "The repository could not be checked for unexpected changes."
                ) from error
    return manifest


def _changed_files(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {
        path
        for path in before.keys() | after.keys()
        if before.get(path) != after.get(path)
    }


def _dry_apply(
    diff_lines: list[str], file: str, original_content: str
) -> tuple[list[Evidence], list[tuple[int, str]], str]:
    newline = "\r\n" if "\r\n" in original_content else "\n"
    has_final_newline = original_content.endswith(("\n", "\r"))
    original = original_content.splitlines()
    output: list[str] = []
    cursor = 0
    index = 0
    original_evidence: list[Evidence] = []
    added_lines: list[tuple[int, str]] = []

    while index < len(diff_lines):
        match = HUNK_HEADER_PATTERN.match(diff_lines[index])
        if match is None:
            raise InvalidPatchError("The unified diff contains unsupported metadata or syntax.")
        old_start = int(match.group("old_start"))
        old_count = int(match.group("old_count") or 1)
        new_count = int(match.group("new_count") or 1)
        target = old_start - 1 if old_start > 0 else 0
        if target < cursor or target > len(original):
            raise InvalidPatchError("The unified diff hunk location is invalid.")
        expected_old = _hunk_original_lines(diff_lines, index + 1)
        if len(expected_old) != old_count:
            raise InvalidPatchError("The unified diff hunk counts are inconsistent.")
        if original[target : target + len(expected_old)] != expected_old:
            exact_matches = [
                position
                for position in range(cursor, len(original) - len(expected_old) + 1)
                if original[position : position + len(expected_old)] == expected_old
            ]
            if len(exact_matches) != 1:
                raise InvalidPatchError("The unified diff does not match the original source.")
            target = exact_matches[0]
        output.extend(original[cursor:target])
        cursor = target
        index += 1
        seen_old = 0
        seen_new = 0
        # Use the position derived from exact source context. Model-generated hunk line numbers
        # can be off by one even when every unchanged line matches byte-for-byte.
        new_line = len(output) + 1
        first_original_line = cursor + 1 if cursor < len(original) else None

        while index < len(diff_lines) and not diff_lines[index].startswith("@@ "):
            line = diff_lines[index]
            if line == r"\ No newline at end of file":
                index += 1
                continue
            if not line or line[0] not in {" ", "+", "-"}:
                raise InvalidPatchError("The unified diff contains an invalid hunk line.")
            marker, text = line[0], line[1:]
            if marker in {" ", "-"}:
                if cursor >= len(original) or original[cursor] != text:
                    raise InvalidPatchError("The unified diff does not match the original source.")
                cursor += 1
                seen_old += 1
            if marker in {" ", "+"}:
                output.append(text)
                seen_new += 1
                if marker == "+":
                    added_lines.append((new_line, text))
                new_line += 1
            index += 1

        if seen_old != old_count or seen_new != new_count:
            raise InvalidPatchError("The unified diff hunk counts are inconsistent.")
        if first_original_line is not None:
            original_evidence.append(
                Evidence(
                    file=file,
                    line=first_original_line,
                    snippet=original[first_original_line - 1].strip(),
                    type=EvidenceType.UI_CONTEXT,
                )
            )

    if not original_evidence:
        raise InvalidPatchError("The unified diff contains no valid hunks.")
    output.extend(original[cursor:])
    proposed_content = newline.join(output)
    if has_final_newline:
        proposed_content += newline
    return original_evidence, added_lines, proposed_content


def _hunk_original_lines(diff_lines: list[str], start: int) -> list[str]:
    original: list[str] = []
    index = start
    while index < len(diff_lines) and not diff_lines[index].startswith("@@ "):
        line = diff_lines[index]
        if line == r"\ No newline at end of file":
            index += 1
            continue
        if not line or line[0] not in {" ", "+", "-"}:
            raise InvalidPatchError("The unified diff contains an invalid hunk line.")
        if line[0] in {" ", "-"}:
            original.append(line[1:])
        index += 1
    return original


_patch_service: PatchService | None = None


def get_patch_service() -> PatchService:
    global _patch_service
    if _patch_service is None:
        _patch_service = PatchService()
    return _patch_service

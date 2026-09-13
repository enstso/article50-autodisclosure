import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import PurePosixPath, PureWindowsPath
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
    PatchNotFoundError,
    PatchTooLargeError,
    RemediationAgentError,
    RemediationContextError,
)
from app.models import (
    Evidence,
    EvidenceType,
    Finding,
    PatchProposal,
    PatchStatus,
    ReadinessStatus,
    RemediationContext,
    RemediationPlan,
)
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


@dataclass(frozen=True)
class ValidatedDiff:
    affected_files: list[str]
    original_snippets: list[Evidence]
    proposed_snippets: list[Evidence]


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
        )


class PatchService:
    def __init__(
        self,
        settings: Settings | None = None,
        remediation_factory: Callable[[], RemediationGenerator] = RemediationAgent,
        validator: UnifiedDiffValidator | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.remediation_factory = remediation_factory
        self.validator = validator or UnifiedDiffValidator(self.settings)
        self._patches: dict[str, PatchProposal] = {}
        self._lock = Lock()

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
            plan = RemediationPlan.model_validate(self.remediation_factory().propose(context))
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
        context_provider.append_event(proposal.scan_id, "Patch approved")
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


def _dry_apply(
    diff_lines: list[str], file: str, original_content: str
) -> tuple[list[Evidence], list[tuple[int, str]], str]:
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
        new_start = int(match.group("new_start"))
        new_count = int(match.group("new_count") or 1)
        target = old_start - 1 if old_start > 0 else 0
        if target < cursor or target > len(original):
            raise InvalidPatchError("The unified diff hunk location is invalid.")
        output.extend(original[cursor:target])
        cursor = target
        index += 1
        seen_old = 0
        seen_new = 0
        new_line = new_start
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
    return original_evidence, added_lines, "\n".join(output)


_patch_service: PatchService | None = None


def get_patch_service() -> PatchService:
    global _patch_service
    if _patch_service is None:
        _patch_service = PatchService()
    return _patch_service

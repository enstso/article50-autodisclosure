from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import Protocol
from uuid import uuid4

from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

from app.agents import (
    AIInteractionInvestigationAgent,
    Article50AnalysisAgent,
    RepositoryInvestigationAgent,
)
from app.core.config import Settings, get_settings
from app.core.exceptions import AutoDisclosureError
from app.models import (
    AIInteractionFlow,
    AIInvestigationResult,
    Article50AnalysisResult,
    Finding,
    FindingResolution,
    PatchProposal,
    ReadinessStatus,
    RemediationContext,
    RepositorySummary,
    Scan,
    ScanStatus,
    SourceSnapshot,
    TransparencyAssessment,
    VerificationResult,
    VerificationStatus,
)
from app.services.article50_service import build_article50_findings
from app.services.repository_service import RepositoryService, validate_repository_url
from app.services.workspace_service import WorkspaceService
from app.tools.disclosure_tools import UI_SUFFIXES
from app.tools.repository_tools import RepositoryInspector


class RepositoryAnalyzer(Protocol):
    def analyze(self, scan_id: str) -> RepositorySummary: ...


class AIInteractionAnalyzer(Protocol):
    def analyze(self, scan_id: str) -> AIInvestigationResult: ...


class Article50Analyzer(Protocol):
    def analyze(
        self, scan_id: str, interactions: list[AIInteractionFlow]
    ) -> Article50AnalysisResult: ...


class ScanService:
    def __init__(
        self,
        settings: Settings | None = None,
        workspace_service: WorkspaceService | None = None,
        repository_service: RepositoryService | None = None,
        analyzer_factory: Callable[[], RepositoryAnalyzer] = RepositoryInvestigationAgent,
        ai_analyzer_factory: Callable[[], AIInteractionAnalyzer] = AIInteractionInvestigationAgent,
        article50_analyzer_factory: Callable[[], Article50Analyzer] = Article50AnalysisAgent,
    ) -> None:
        self.settings = settings or get_settings()
        self.workspace_service = workspace_service or WorkspaceService(self.settings)
        self.repository_service = repository_service or RepositoryService(self.settings)
        self.analyzer_factory = analyzer_factory
        self.ai_analyzer_factory = ai_analyzer_factory
        self.article50_analyzer_factory = article50_analyzer_factory
        self._scans: dict[str, Scan] = {}
        self._remediation_contexts: dict[str, RemediationContext] = {}
        self._lock = Lock()

    def create_scan(self, repository_url: str) -> Scan:
        scan = Scan(id=str(uuid4()), repository_url=repository_url.strip())
        self._save(scan)
        workspace_created = False

        try:
            scan.repository_url = validate_repository_url(repository_url)
            scan.events.append("Repository URL validated")

            self.workspace_service.create_workspace(scan.id)
            workspace_created = True
            scan.status = ScanStatus.CLONING
            scan.events.append("Cloning public GitHub repository")
            self._save(scan)

            repository_path = self.workspace_service.get_repository_path(scan.id)
            self.repository_service.clone_repository(scan.repository_url, repository_path)
            metadata = self.repository_service.get_repository_metadata(repository_path)
            scan.events.append(f"Repository cloned at commit {str(metadata['commit'])[:7]}")

            scan.status = ScanStatus.ANALYZING
            scan.events.append("Repository agent started")
            scan.events.append("Inspecting repository structure and relevant source files")
            self._save(scan)

            summary = self.analyzer_factory().analyze(scan.id)
            scan.summary = RepositorySummary.model_validate(summary)

            scan.events.append("Searching for AI dependencies and model invocations")
            self._save(scan)
            investigation = self.ai_analyzer_factory().analyze(scan.id)
            validated_investigation = AIInvestigationResult.model_validate(investigation)
            scan.ai_usages = validated_investigation.ai_usages
            scan.ai_interactions = validated_investigation.ai_interactions
            for usage in scan.ai_usages:
                scan.events.append(f"Detected {usage.provider or 'AI'} usage in {usage.file}")
            for interaction in scan.ai_interactions:
                if interaction.api_endpoint:
                    scan.events.append(f"Detected {interaction.api_endpoint}")
                if interaction.frontend_entrypoint:
                    scan.events.append(
                        f"Found frontend caller in {interaction.frontend_entrypoint}"
                    )
                scan.events.append(
                    "AI interaction confirmed"
                    if interaction.user_facing
                    else "AI interaction remains incomplete or non-user-facing"
                )

            scan.events.append("Evaluating Article 50 transparency readiness")
            scan.events.append("Inspecting user-facing AI interface")
            scan.events.append("Searching for AI disclosure")
            self._save(scan)
            article50_result = self.article50_analyzer_factory().analyze(
                scan.id, scan.ai_interactions
            )
            validated_article50 = Article50AnalysisResult.model_validate(article50_result)
            scan.article50_assessments = validated_article50.assessments
            scan.findings = build_article50_findings(
                scan.article50_assessments, scan.ai_interactions
            )
            self._capture_remediation_contexts(scan)
            for assessment in scan.article50_assessments:
                if assessment.status == ReadinessStatus.PASS:
                    scan.events.append("AI disclosure detected")
                    scan.events.append("Article 50 readiness check passed")
                elif assessment.status == ReadinessStatus.ACTION_REQUIRED:
                    scan.events.append("No relevant disclosure found")
                    scan.events.append("Potential transparency gap detected")
                else:
                    scan.events.append("Manual transparency review recommended")
            scan.status = _readiness_scan_status(scan.article50_assessments)
            scan.events.append("Repository analysis completed")
        except Exception as error:  # Errors are converted to a deliberately small safe vocabulary.
            scan.status = ScanStatus.FAILED
            scan.error = _safe_error_message(error)
            scan.events.append("Repository analysis failed")
        finally:
            retain_for_remediation = any(
                finding.remediation_available for finding in scan.findings
            )
            if workspace_created and not retain_for_remediation:
                try:
                    self.workspace_service.cleanup_workspace(scan.id)
                except OSError:
                    # Cleanup failure is operational and must not leak a local path to API clients.
                    pass
            self._save(scan)

        return scan.model_copy(deep=True)

    def get_scan(self, scan_id: str) -> Scan | None:
        with self._lock:
            scan = self._scans.get(scan_id)
            return scan.model_copy(deep=True) if scan else None

    def get_finding(self, finding_id: str) -> tuple[str, Finding] | None:
        with self._lock:
            for scan in self._scans.values():
                finding = next((item for item in scan.findings if item.id == finding_id), None)
                if finding is not None:
                    return scan.id, finding.model_copy(deep=True)
        return None

    def get_remediation_context(self, finding_id: str) -> RemediationContext | None:
        with self._lock:
            context = self._remediation_contexts.get(finding_id)
            return context.model_copy(deep=True) if context is not None else None

    def link_patch_proposal(self, finding_id: str, patch_id: str) -> None:
        with self._lock:
            for scan in self._scans.values():
                for index, finding in enumerate(scan.findings):
                    if finding.id == finding_id:
                        scan.findings[index] = finding.model_copy(
                            update={"patch_proposal_id": patch_id}, deep=True
                        )
                        return
        raise ValueError("Finding not found while linking patch proposal.")

    def append_event(self, scan_id: str, event: str) -> None:
        with self._lock:
            scan = self._scans.get(scan_id)
            if scan is not None:
                scan.events.append(event)

    def verify_patch(self, proposal: PatchProposal) -> VerificationResult:
        context = self.get_remediation_context(proposal.finding_id)
        scan = self.get_scan(proposal.scan_id)
        if context is None or scan is None or context.scan_id != proposal.scan_id:
            raise ValueError("Patch verification context is unavailable.")

        previous_status = context.assessment.status
        self.append_event(proposal.scan_id, "Verifying transparency disclosure")
        try:
            result = self.article50_analyzer_factory().analyze(
                proposal.scan_id, [context.interaction]
            )
            validated = Article50AnalysisResult.model_validate(result)
            assessment = next(
                (
                    item
                    for item in validated.assessments
                    if item.interaction_id == context.interaction.id
                ),
                None,
            )
            if assessment is None:
                raise ValueError("Targeted verification returned no matching assessment.")
        except Exception:
            verification = VerificationResult(
                id=str(uuid4()),
                patch_id=proposal.id,
                scan_id=proposal.scan_id,
                finding_id=proposal.finding_id,
                status=VerificationStatus.NEEDS_REVIEW,
                previous_readiness_status=previous_status,
                new_readiness_status=previous_status,
                disclosure_detected=None,
                explanation=(
                    "The patch was applied, but automated transparency verification could not "
                    "complete. Manual review is required."
                ),
                evidence=[],
                verified_at=datetime.now(UTC),
            )
            self.append_event(proposal.scan_id, "Verification needs review")
            return verification

        if (
            previous_status == ReadinessStatus.ACTION_REQUIRED
            and assessment.status == ReadinessStatus.PASS
        ):
            verification_status = VerificationStatus.PASSED
            explanation = (
                "The approved disclosure was applied and the user-facing AI interaction now "
                "contains an explicit AI transparency notice."
            )
        elif assessment.status == ReadinessStatus.NEEDS_REVIEW:
            verification_status = VerificationStatus.NEEDS_REVIEW
            explanation = (
                "The patch was applied, but the transparency outcome still requires manual review."
            )
        else:
            verification_status = VerificationStatus.FAILED
            explanation = (
                "The patch was applied, but the AI interaction still requires an explicit "
                "transparency disclosure."
            )

        verification = VerificationResult(
            id=str(uuid4()),
            patch_id=proposal.id,
            scan_id=proposal.scan_id,
            finding_id=proposal.finding_id,
            status=verification_status,
            previous_readiness_status=previous_status,
            new_readiness_status=assessment.status,
            disclosure_detected=assessment.disclosure_detected,
            explanation=explanation,
            evidence=assessment.evidence,
            verified_at=datetime.now(UTC),
        )
        self._store_verification_assessment(proposal, assessment, verification)
        return verification

    def _store_verification_assessment(
        self,
        proposal: PatchProposal,
        assessment: TransparencyAssessment,
        verification: VerificationResult,
    ) -> None:
        with self._lock:
            scan = self._scans.get(proposal.scan_id)
            if scan is None:
                raise ValueError("Scan not found while storing patch verification.")
            for index, current in enumerate(scan.article50_assessments):
                if current.interaction_id == assessment.interaction_id:
                    scan.article50_assessments[index] = assessment.model_copy(deep=True)
                    break
            for index, finding in enumerate(scan.findings):
                if finding.id != proposal.finding_id:
                    continue
                resolved = verification.status == VerificationStatus.PASSED
                scan.findings[index] = finding.model_copy(
                    update={
                        "status": assessment.status,
                        "resolution": (
                            FindingResolution.RESOLVED if resolved else FindingResolution.OPEN
                        ),
                        "explanation": assessment.explanation,
                        "evidence": assessment.evidence,
                        "remediation_available": False,
                    },
                    deep=True,
                )
                break
            scan.status = _readiness_scan_status(scan.article50_assessments)
            if verification.status == VerificationStatus.PASSED:
                scan.events.append("AI disclosure detected")
                scan.events.append("Verification passed")
            elif verification.status == VerificationStatus.FAILED:
                scan.events.append("Patch verification failed")
            else:
                scan.events.append("Verification needs review")

    def _capture_remediation_contexts(self, scan: Scan) -> None:
        assessments = {
            assessment.interaction_id: assessment
            for assessment in scan.article50_assessments
        }
        interactions = {interaction.id: interaction for interaction in scan.ai_interactions}
        repository = RepositoryInspector(self.settings, self.workspace_service)
        contexts: dict[str, RemediationContext] = {}
        for index, finding in enumerate(scan.findings):
            if finding.status != ReadinessStatus.ACTION_REQUIRED:
                continue
            interaction_id = finding.id.removeprefix("article50-")
            assessment = assessments.get(interaction_id)
            interaction = interactions.get(interaction_id)
            if assessment is None or interaction is None or not interaction.frontend_entrypoint:
                continue
            entrypoint = interaction.frontend_entrypoint.replace("\\", "/")
            entrypoint_parts = entrypoint.casefold().split("/")
            if (
                Path(entrypoint).suffix.casefold() not in UI_SUFFIXES
                or "backend" in entrypoint_parts
                or entrypoint not in finding.affected_files
            ):
                continue
            try:
                source = repository.read_source_file(
                    scan.id, entrypoint
                )
            except (AutoDisclosureError, OSError, ValueError):
                continue
            content = source["content"]
            updated_finding = finding.model_copy(update={"remediation_available": True})
            scan.findings[index] = updated_finding
            contexts[finding.id] = RemediationContext(
                scan_id=scan.id,
                finding=updated_finding,
                assessment=assessment,
                interaction=interaction,
                source_files=[
                    SourceSnapshot(
                        file=source["path"],
                        content=content,
                        sha256=sha256(content.encode("utf-8")).hexdigest(),
                    )
                ],
            )
        with self._lock:
            self._remediation_contexts.update(contexts)

    def _save(self, scan: Scan) -> None:
        with self._lock:
            self._scans[scan.id] = scan.model_copy(deep=True)


def _safe_error_message(error: Exception) -> str:
    if isinstance(error, AutoDisclosureError):
        return str(error)
    if isinstance(error, (NoCredentialsError, PartialCredentialsError)):
        return "Amazon Bedrock authentication is not configured."
    if isinstance(error, ClientError):
        code = str(error.response.get("Error", {}).get("Code", ""))
        if code in {"AccessDenied", "AccessDeniedException", "UnauthorizedException"}:
            return (
                "Amazon Bedrock access was denied. "
                "Account verification or model access may be pending."
            )
        if code in {
            "ResourceNotFoundException",
            "ModelNotReadyException",
            "ModelTimeoutException",
            "ValidationException",
        }:
            return "The configured Amazon Bedrock model is unavailable."

    lowered = str(error).lower()
    if "credential" in lowered or "authentication" in lowered:
        return "Amazon Bedrock authentication is not configured."
    if "accessdenied" in lowered or "access denied" in lowered or "being verified" in lowered:
        return (
            "Amazon Bedrock access was denied. Account verification or model access may be pending."
        )
    if "model" in lowered and ("unavailable" in lowered or "not found" in lowered):
        return "The configured Amazon Bedrock model is unavailable."
    return "Repository analysis failed."


def _readiness_scan_status(
    assessments: list[TransparencyAssessment],
) -> ScanStatus:
    statuses = {assessment.status for assessment in assessments}
    if ReadinessStatus.ACTION_REQUIRED in statuses:
        return ScanStatus.ACTION_REQUIRED
    if assessments and statuses == {ReadinessStatus.PASS}:
        return ScanStatus.PASS
    return ScanStatus.COMPLETED


_scan_service: ScanService | None = None


def get_scan_service() -> ScanService:
    global _scan_service
    if _scan_service is None:
        _scan_service = ScanService()
    return _scan_service

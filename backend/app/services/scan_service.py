from collections.abc import Callable
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
    ReadinessStatus,
    RepositorySummary,
    Scan,
    ScanStatus,
    TransparencyAssessment,
)
from app.services.article50_service import build_article50_findings
from app.services.repository_service import RepositoryService, validate_repository_url
from app.services.workspace_service import WorkspaceService


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
            if workspace_created:
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

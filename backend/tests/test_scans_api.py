import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.models import (
    AIInteractionFlow,
    AIInvestigationResult,
    AIUsage,
    Article50AnalysisResult,
    Evidence,
    EvidenceType,
    ReadinessStatus,
    RemediationPlan,
    RepositorySummary,
    ScanStatus,
    TransparencyAssessment,
)
from app.services.patch_service import PatchService, get_patch_service
from app.services.scan_service import ScanService, get_scan_service
from app.services.workspace_service import WorkspaceService

FIXTURE_REPOSITORY = Path(__file__).parent / "fixtures" / "sample_repository"


class FakeRepositoryService:
    def clone_repository(self, repository_url: str, destination: Path) -> Path:
        shutil.copytree(FIXTURE_REPOSITORY, destination)
        return destination

    def get_repository_metadata(self, repository_path: Path) -> dict[str, str | int]:
        return {"commit": "abcdef123456", "branch": "main", "size_bytes": 100}


class FakeAnalyzer:
    def analyze(self, scan_id: str) -> RepositorySummary:
        return RepositorySummary(
            languages=["TypeScript", "Python"],
            frameworks=["React", "FastAPI"],
            architecture_summary="React frontend communicating with a FastAPI backend.",
            important_files=["frontend/package.json", "backend/app/main.py"],
            potential_ai_integrations=[],
        )


class FakeAIAnalyzer:
    def analyze(self, scan_id: str) -> AIInvestigationResult:
        model_evidence = Evidence(
            file="backend/app/main.py",
            line=1,
            snippet="from fastapi import FastAPI",
            type=EvidenceType.MODEL_CALL,
        )
        return AIInvestigationResult(
            ai_usages=[
                AIUsage(
                    provider="Amazon Bedrock",
                    sdk="boto3",
                    model=None,
                    file="backend/app/main.py",
                    line=1,
                    purpose="Fixture result",
                    evidence=[model_evidence],
                    confidence=0.9,
                )
            ],
            ai_interactions=[
                AIInteractionFlow(
                    id="fixture-flow",
                    name="Fixture interaction",
                    user_facing=True,
                    frontend_entrypoint="frontend/src/App.tsx",
                    api_endpoint="POST /api/chat",
                    backend_handler="backend/app/main.py",
                    ai_provider="Amazon Bedrock",
                    ai_model=None,
                    flow_summary="Fixture API serialization flow.",
                    evidence=[model_evidence],
                    confidence=0.9,
                )
            ],
        )


class FakeArticle50Analyzer:
    def analyze(self, scan_id: str, interactions: list[AIInteractionFlow]):
        return Article50AnalysisResult(
            assessments=[
                TransparencyAssessment(
                    interaction_id=interactions[0].id,
                    rule_id="ARTICLE_50_1_AI_INTERACTION_DISCLOSURE",
                    status=ReadinessStatus.ACTION_REQUIRED,
                    disclosure_detected=False,
                    explanation=(
                        "A direct user-facing AI interaction was detected, but no clear "
                        "transparency disclosure was found in the relevant interface."
                    ),
                    evidence=interactions[0].evidence,
                    inspected_files=["frontend/src/App.tsx"],
                    confidence=0.9,
                )
            ]
        )


class FakeRemediationGenerator:
    def propose(self, context) -> RemediationPlan:
        return RemediationPlan(
            title="Add AI disclosure to fixture interface",
            rationale="Adds an explicit notice in the existing main element.",
            disclosure_text="You are interacting with an AI assistant.",
            affected_files=["frontend/src/App.tsx"],
            unified_diff="""--- a/frontend/src/App.tsx
+++ b/frontend/src/App.tsx
@@ -1,3 +1,8 @@
 export function App() {
-  return <main>Fixture application</main>;
+  return (
+    <main>
+      <p>You are interacting with an AI assistant.</p>
+      Fixture application
+    </main>
+  );
 }
""",
            confidence=0.92,
        )


@pytest.fixture
def client(tmp_path):
    settings = Settings(workspace_path=tmp_path)
    service = ScanService(
        settings=settings,
        workspace_service=WorkspaceService(settings),
        repository_service=FakeRepositoryService(),
        analyzer_factory=FakeAnalyzer,
        ai_analyzer_factory=FakeAIAnalyzer,
        article50_analyzer_factory=FakeArticle50Analyzer,
    )
    patch_service = PatchService(
        settings=settings,
        remediation_factory=FakeRemediationGenerator,
    )
    app.dependency_overrides[get_scan_service] = lambda: service
    app.dependency_overrides[get_patch_service] = lambda: patch_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_and_get_scan_without_network_or_aws(client: TestClient) -> None:
    response = client.post(
        "/api/scans",
        json={"repository_url": "https://github.com/example/repository.git"},
    )

    assert response.status_code == 201
    scan = response.json()
    assert scan["repository_url"] == "https://github.com/example/repository"
    assert scan["status"] == ScanStatus.ACTION_REQUIRED
    assert scan["summary"]["frameworks"] == ["React", "FastAPI"]
    assert scan["ai_usages"][0]["provider"] == "Amazon Bedrock"
    assert scan["ai_interactions"][0]["user_facing"] is True
    assert scan["ai_interactions"][0]["evidence"][0]["line"] == 1
    assert scan["article50_assessments"][0]["status"] == "ACTION_REQUIRED"
    assert scan["findings"][0]["title"] == "Missing AI interaction disclosure"
    assert scan["findings"][0]["remediation_available"] is True
    assert scan["error"] is None
    assert scan["events"][-1] == "Repository analysis completed"

    get_response = client.get(f"/api/scans/{scan['id']}")
    assert get_response.status_code == 200
    assert get_response.json() == scan


def test_create_scan_returns_safe_failure_for_invalid_url(client: TestClient) -> None:
    response = client.post("/api/scans", json={"repository_url": "file:///etc/passwd"})

    assert response.status_code == 201
    scan = response.json()
    assert scan["status"] == ScanStatus.FAILED
    assert scan["summary"] is None
    assert "github.com" in scan["error"]
    assert "Traceback" not in scan["error"]


def test_get_unknown_scan_returns_controlled_404(client: TestClient) -> None:
    response = client.get("/api/scans/unknown")

    assert response.status_code == 404
    assert response.json() == {"detail": "Scan not found."}


def test_generate_and_approve_patch_without_applying_repository_changes(
    client: TestClient,
) -> None:
    scan = client.post(
        "/api/scans",
        json={"repository_url": "https://github.com/example/repository"},
    ).json()
    finding_id = scan["findings"][0]["id"]

    generated_response = client.post(f"/api/findings/{finding_id}/patch")

    assert generated_response.status_code == 201
    proposal = generated_response.json()
    assert proposal["status"] == "READY_FOR_REVIEW"
    assert proposal["affected_files"] == ["frontend/src/App.tsx"]
    assert proposal["unified_diff"]
    assert proposal["disclosure_text"] == "You are interacting with an AI assistant."

    approved_response = client.post(f"/api/patches/{proposal['id']}/approve")

    assert approved_response.status_code == 200
    assert approved_response.json()["status"] == "APPROVED"
    assert approved_response.json()["approved_at"] is not None
    updated_scan = client.get(f"/api/scans/{scan['id']}").json()
    assert updated_scan["findings"][0]["patch_proposal_id"] == proposal["id"]
    assert updated_scan["events"][-1] == "Patch approved"

    invalid_transition = client.post(f"/api/patches/{proposal['id']}/reject")
    assert invalid_transition.status_code == 409


def test_reject_patch_and_unknown_resources_are_controlled(client: TestClient) -> None:
    scan = client.post(
        "/api/scans",
        json={"repository_url": "https://github.com/example/repository"},
    ).json()
    finding_id = scan["findings"][0]["id"]
    proposal = client.post(f"/api/findings/{finding_id}/patch").json()

    rejected = client.post(
        f"/api/patches/{proposal['id']}/reject",
        json={"reason": "Use different wording."},
    )

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["rejection_reason"] == "Use different wording."
    assert client.post("/api/findings/unknown/patch").status_code == 404
    assert client.get("/api/patches/unknown").status_code == 404

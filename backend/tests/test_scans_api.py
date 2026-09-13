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
    Evidence,
    EvidenceType,
    RepositorySummary,
    ScanStatus,
)
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


@pytest.fixture
def client(tmp_path):
    settings = Settings(workspace_path=tmp_path)
    service = ScanService(
        settings=settings,
        workspace_service=WorkspaceService(settings),
        repository_service=FakeRepositoryService(),
        analyzer_factory=FakeAnalyzer,
        ai_analyzer_factory=FakeAIAnalyzer,
    )
    app.dependency_overrides[get_scan_service] = lambda: service
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
    assert scan["status"] == ScanStatus.COMPLETED
    assert scan["summary"]["frameworks"] == ["React", "FastAPI"]
    assert scan["ai_usages"][0]["provider"] == "Amazon Bedrock"
    assert scan["ai_interactions"][0]["user_facing"] is True
    assert scan["ai_interactions"][0]["evidence"][0]["line"] == 1
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

import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models import AIInvestigationResult
from app.services.evidence_service import InvestigationResultValidator
from app.services.workspace_service import WorkspaceService
from app.tools.ai_detection_tools import AIDetectionInspector
from app.tools.repository_tools import RepositoryInspector

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture_inspectors(tmp_path, fixture_name: str):
    settings = Settings(workspace_path=tmp_path)
    workspace = WorkspaceService(settings)
    scan_id = str(uuid4())
    workspace.create_workspace(scan_id)
    shutil.copytree(FIXTURES / fixture_name, workspace.get_repository_path(scan_id))
    repository = RepositoryInspector(settings, workspace)
    return scan_id, repository, AIDetectionInspector(settings, repository)


def test_detect_ai_usage_finds_bedrock_with_real_line_evidence(tmp_path) -> None:
    scan_id, _, detector = _fixture_inspectors(tmp_path, "ai_chat_app")

    result = detector.detect_ai_usage(scan_id)

    assert {
        "provider": "Amazon Bedrock",
        "package": "boto3",
        "file": "backend/requirements.txt",
        "line": 2,
        "snippet": "boto3>=1.40",
    } in result["dependencies"]
    assert {
        "provider": "Amazon Bedrock",
        "pattern": "bedrock-runtime client",
        "kind": "client",
        "file": "backend/app/services/ai.py",
        "line": 3,
        "snippet": 'bedrock = boto3.client("bedrock-runtime")',
    } in result["usage_candidates"]
    assert any(
        candidate["provider"] == "Amazon Bedrock"
        and candidate["kind"] == "invocation"
        and candidate["file"] == "backend/app/services/ai.py"
        and candidate["line"] == 7
        for candidate in result["usage_candidates"]
    )


def test_detect_ai_usage_supports_anthropic_openai_and_bedrock_sdk(tmp_path) -> None:
    scan_id, _, detector = _fixture_inspectors(tmp_path, "provider_signals")

    result = detector.detect_ai_usage(scan_id)
    dependencies = {(item["provider"], item["package"]) for item in result["dependencies"]}
    candidates = result["usage_candidates"]

    assert ("Anthropic", "anthropic") in dependencies
    assert ("OpenAI", "openai") in dependencies
    assert ("Amazon Bedrock", "@aws-sdk/client-bedrock-runtime") in dependencies
    assert any(
        item["provider"] == "Anthropic"
        and item["file"] == "providers.py"
        and item["line"] == 1
        and item["snippet"] == "from anthropic import Anthropic"
        for item in candidates
    )
    assert any(
        item["provider"] == "OpenAI"
        and item["file"] == "providers.py"
        and item["line"] == 2
        and item["snippet"] == "from openai import OpenAI"
        for item in candidates
    )


def test_find_fastapi_route_endpoint_caller_and_symbol_references(tmp_path) -> None:
    scan_id, _, detector = _fixture_inspectors(tmp_path, "ai_chat_app")

    routes = detector.find_api_routes(scan_id)
    callers = detector.search_endpoint_usage(scan_id, "/api/chat")
    references = detector.find_symbol_references(scan_id, "generate_reply")

    assert {
        "method": "POST",
        "path": "/api/chat",
        "file": "backend/app/api/chat.py",
        "line": 7,
        "snippet": '@router.post("/api/chat")',
    } in routes
    assert callers == [
        {
            "file": "frontend/src/Chat.tsx",
            "line": 7,
            "snippet": 'const response = await fetch("/api/chat", {',
        }
    ]
    assert {
        "file": "backend/app/api/chat.py",
        "line": 9,
        "snippet": 'return {"reply": generate_reply(payload["message"])}',
    } in references


def test_dependency_and_readme_mentions_do_not_become_ai_usage(tmp_path) -> None:
    settings = Settings(workspace_path=tmp_path)
    workspace = WorkspaceService(settings)
    scan_id = str(uuid4())
    workspace.create_workspace(scan_id)
    repository_path = workspace.get_repository_path(scan_id)
    repository_path.mkdir()
    (repository_path / "requirements.txt").write_text("openai>=1.0\n", encoding="utf-8")
    (repository_path / "README.md").write_text(
        "This document discusses OpenAI and responses.create but contains no application code.",
        encoding="utf-8",
    )
    repository = RepositoryInspector(settings, workspace)
    detector = AIDetectionInspector(settings, repository)

    signals = detector.detect_ai_usage(scan_id)
    validated = InvestigationResultValidator(repository, detector).validate(
        scan_id,
        AIInvestigationResult(),
    )

    assert len(signals["dependencies"]) == 1
    assert signals["usage_candidates"] == []
    assert validated.ai_usages == []
    assert validated.ai_interactions == []


def test_background_model_invocation_is_usage_without_confirmed_flow(tmp_path) -> None:
    settings = Settings(workspace_path=tmp_path)
    workspace = WorkspaceService(settings)
    scan_id = str(uuid4())
    workspace.create_workspace(scan_id)
    repository_path = workspace.get_repository_path(scan_id)
    (repository_path / "backend" / "jobs").mkdir(parents=True)
    (repository_path / "backend" / "jobs" / "summarizer.py").write_text(
        "from openai import OpenAI\n"
        "client = OpenAI()\n"
        'result = client.responses.create(model="gpt-4.1", input="daily report")\n',
        encoding="utf-8",
    )
    repository = RepositoryInspector(settings, workspace)
    detector = AIDetectionInspector(settings, repository)

    validated = InvestigationResultValidator(repository, detector).validate(
        scan_id,
        AIInvestigationResult(),
    )

    assert len(validated.ai_usages) == 1
    assert validated.ai_usages[0].provider == "OpenAI"
    assert validated.ai_interactions == []


@pytest.mark.parametrize("endpoint", ["", "chat", "https://localhost/api/chat"])
def test_endpoint_search_rejects_non_relative_endpoints(tmp_path, endpoint: str) -> None:
    scan_id, _, detector = _fixture_inspectors(tmp_path, "ai_chat_app")

    with pytest.raises(ValueError):
        detector.search_endpoint_usage(scan_id, endpoint)

import shutil
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agents.article50_agent import ARTICLE50_SYSTEM_PROMPT, Article50AnalysisAgent
from app.core.config import Settings
from app.core.exceptions import RepositoryAgentError
from app.models import Article50AnalysisResult, ReadinessStatus
from app.services.workspace_service import WorkspaceService
from tests.test_disclosure_tools import _interaction

FIXTURE = Path(__file__).parent / "fixtures" / "ai_chat_app_disclosed"


def test_article50_agent_uses_targeted_read_only_tools_and_grounded_validation(
    tmp_path: Path,
) -> None:
    settings = Settings(workspace_path=tmp_path)
    workspace = WorkspaceService(settings)
    scan_id = str(uuid4())
    workspace.create_workspace(scan_id)
    shutil.copytree(FIXTURE, workspace.get_repository_path(scan_id))
    captured: dict[str, object] = {}

    class FakeAgent:
        def __init__(self, **kwargs) -> None:
            captured["configuration"] = kwargs

        def __call__(self, prompt: str, **kwargs):
            captured["prompt"] = prompt
            return SimpleNamespace(structured_output=Article50AnalysisResult())

    analyzer = Article50AnalysisAgent(
        settings=settings,
        model_factory=lambda: object(),
        agent_factory=FakeAgent,
    )
    result = analyzer.analyze(scan_id, [_interaction()])

    configuration = captured["configuration"]
    assert len(configuration["tools"]) == 5
    assert configuration["system_prompt"] == ARTICLE50_SYSTEM_PROMPT
    assert "chat-interaction" in captured["prompt"]
    assert result.assessments[0].status == ReadinessStatus.PASS
    assert result.assessments[0].disclosure_file == "frontend/src/Chat.tsx"


def test_article50_agent_accepts_valid_json_structured_output(tmp_path: Path) -> None:
    settings = Settings(workspace_path=tmp_path)
    workspace = WorkspaceService(settings)
    scan_id = str(uuid4())
    workspace.create_workspace(scan_id)
    source = Path(__file__).parent / "fixtures" / "ai_chat_app"
    shutil.copytree(source, workspace.get_repository_path(scan_id))

    class FakeAgent:
        def __init__(self, **kwargs) -> None:
            pass

        def __call__(self, prompt: str, **kwargs):
            return SimpleNamespace(structured_output='{"assessments": []}')

    analyzer = Article50AnalysisAgent(
        settings=settings,
        model_factory=lambda: object(),
        agent_factory=FakeAgent,
    )

    result = analyzer.analyze(scan_id, [_interaction()])

    assert len(result.assessments) == 1
    assert result.assessments[0].status == ReadinessStatus.ACTION_REQUIRED


def test_article50_agent_rejects_malformed_output_explicitly(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    settings = Settings(workspace_path=tmp_path)
    workspace = WorkspaceService(settings)
    scan_id = str(uuid4())
    workspace.create_workspace(scan_id)
    source = Path(__file__).parent / "fixtures" / "ai_chat_app"
    shutil.copytree(source, workspace.get_repository_path(scan_id))

    class FakeAgent:
        def __init__(self, **kwargs) -> None:
            pass

        def __call__(self, prompt: str, **kwargs):
            return SimpleNamespace(structured_output="not valid JSON")

    analyzer = Article50AnalysisAgent(
        settings=settings,
        model_factory=lambda: object(),
        agent_factory=FakeAgent,
    )

    with pytest.raises(RepositoryAgentError, match="invalid structured result"):
        analyzer.analyze(scan_id, [_interaction()])

    assert "structured output validation failed" in caplog.text
    assert "not valid JSON" not in caplog.text


def test_background_interaction_does_not_invoke_article50_agent(tmp_path: Path) -> None:
    settings = Settings(workspace_path=tmp_path)

    class UnexpectedAgent:
        def __init__(self, **kwargs) -> None:
            raise AssertionError("Background interactions must not invoke Article 50 analysis")

    analyzer = Article50AnalysisAgent(
        settings=settings,
        model_factory=lambda: object(),
        agent_factory=UnexpectedAgent,
    )
    background = _interaction().model_copy(update={"user_facing": False})

    result = analyzer.analyze("background-scan", [background])

    assert result.assessments == []

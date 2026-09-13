import shutil
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from app.agents.article50_agent import ARTICLE50_SYSTEM_PROMPT, Article50AnalysisAgent
from app.core.config import Settings
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

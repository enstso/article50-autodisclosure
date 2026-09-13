from types import SimpleNamespace

from app.agents.repository_agent import (
    REPOSITORY_AGENT_SYSTEM_PROMPT,
    RepositoryInvestigationAgent,
)
from app.models import RepositorySummary


def test_repository_agent_uses_strands_tools_and_structured_output() -> None:
    captured: dict[str, object] = {}
    expected = RepositorySummary(
        languages=["Python"],
        frameworks=["FastAPI"],
        architecture_summary="A FastAPI service.",
        important_files=["backend/app/main.py"],
    )

    class FakeAgent:
        def __init__(self, **kwargs) -> None:
            captured["configuration"] = kwargs

        def __call__(self, prompt: str, **kwargs):
            captured["prompt"] = prompt
            captured["invocation"] = kwargs
            return SimpleNamespace(structured_output=expected)

    analyzer = RepositoryInvestigationAgent(
        model_factory=lambda: object(),
        agent_factory=FakeAgent,
    )

    result = analyzer.analyze("00000000-0000-0000-0000-000000000000")

    configuration = captured["configuration"]
    assert result == expected
    assert len(configuration["tools"]) == 4
    assert configuration["structured_output_model"] is RepositorySummary
    assert configuration["system_prompt"] == REPOSITORY_AGENT_SYSTEM_PROMPT
    assert "Begin with the repository structure" in captured["prompt"]

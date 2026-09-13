from types import SimpleNamespace

from app.agents.remediation_agent import REMEDIATION_SYSTEM_PROMPT, RemediationAgent
from app.models import RemediationPlan
from tests.test_patch_service import _context, _plan


def test_remediation_agent_receives_only_bounded_read_only_context() -> None:
    captured: dict[str, object] = {}

    class FakeAgent:
        def __init__(self, **kwargs) -> None:
            captured["configuration"] = kwargs

        def __call__(self, prompt: str, **kwargs):
            captured["prompt"] = prompt
            return SimpleNamespace(structured_output=_plan())

    agent = RemediationAgent(
        model_factory=lambda: object(),
        agent_factory=FakeAgent,
    )
    result = agent.propose(_context())

    assert isinstance(result, RemediationPlan)
    assert captured["configuration"]["system_prompt"] == REMEDIATION_SYSTEM_PROMPT
    assert len(captured["configuration"]["tools"]) == 1
    assert "finding-1" in captured["prompt"]
    assert result.affected_files == ["frontend/src/Chat.tsx"]

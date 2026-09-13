import pytest
from pydantic import ValidationError

from app.models import AIInteractionFlow, AIUsage, Finding, ReadinessStatus


def test_finding_confidence_must_be_between_zero_and_one() -> None:
    with pytest.raises(ValidationError):
        Finding(
            id="finding-1",
            rule="article-50-disclosure",
            severity="high",
            title="Missing disclosure",
            explanation="No transparency notice was found.",
            evidence=[],
            affected_files=["src/chat.tsx"],
            confidence=1.1,
            status=ReadinessStatus.ACTION_REQUIRED,
        )


@pytest.mark.parametrize(
    "model",
    [
        lambda: AIUsage(
            file="service.py",
            evidence=[],
            confidence=-0.01,
        ),
        lambda: AIInteractionFlow(
            id="flow",
            name="Chat",
            user_facing=True,
            flow_summary="A chat flow.",
            evidence=[],
            confidence=1.01,
        ),
    ],
)
def test_ai_result_confidence_is_bounded(model) -> None:
    with pytest.raises(ValidationError):
        model()

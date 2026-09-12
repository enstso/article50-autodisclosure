import pytest
from pydantic import ValidationError

from app.models import Finding


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
        )


import pytest

from app.core.article50_rules import PRIMARY_ARTICLE50_RULE
from app.models import ReadinessStatus, ScanStatus, TransparencyAssessment
from app.services.scan_service import _readiness_scan_status


def _assessment(status: ReadinessStatus) -> TransparencyAssessment:
    return TransparencyAssessment(
        interaction_id=f"interaction-{status.value}",
        rule_id=PRIMARY_ARTICLE50_RULE.id,
        status=status,
        disclosure_detected=(
            True
            if status == ReadinessStatus.PASS
            else False
            if status == ReadinessStatus.ACTION_REQUIRED
            else None
        ),
        explanation="Evidence-backed readiness outcome.",
        confidence=0.9,
    )


def test_primary_rule_metadata_is_centralized() -> None:
    assert PRIMARY_ARTICLE50_RULE.id == "ARTICLE_50_1_AI_INTERACTION_DISCLOSURE"
    assert PRIMARY_ARTICLE50_RULE.source_reference.endswith("Article 50(1)")
    assert PRIMARY_ARTICLE50_RULE.source_url.startswith("https://eur-lex.europa.eu/")


@pytest.mark.parametrize(
    ("assessments", "expected"),
    [
        ([], ScanStatus.COMPLETED),
        ([_assessment(ReadinessStatus.PASS)], ScanStatus.PASS),
        ([_assessment(ReadinessStatus.NEEDS_REVIEW)], ScanStatus.COMPLETED),
        (
            [
                _assessment(ReadinessStatus.PASS),
                _assessment(ReadinessStatus.ACTION_REQUIRED),
            ],
            ScanStatus.ACTION_REQUIRED,
        ),
    ],
)
def test_readiness_status_maps_to_scan_status(assessments, expected: ScanStatus) -> None:
    assert _readiness_scan_status(assessments) == expected

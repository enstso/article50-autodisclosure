from app.core.article50_rules import PRIMARY_ARTICLE50_RULE
from app.models import (
    AIInteractionFlow,
    Article50AnalysisResult,
    Evidence,
    EvidenceType,
    Finding,
    ReadinessStatus,
    TransparencyAssessment,
)
from app.services.evidence_service import EvidenceService, _unique_evidence
from app.tools.disclosure_tools import DisclosureInspector


class TransparencyAssessmentValidator:
    """Ground Article 50 readiness outcomes in deterministic repository evidence."""

    def __init__(self, disclosure: DisclosureInspector) -> None:
        self.disclosure = disclosure
        self.evidence = EvidenceService(disclosure.repository)

    def validate(
        self,
        scan_id: str,
        interactions: list[AIInteractionFlow],
        proposed: Article50AnalysisResult,
    ) -> Article50AnalysisResult:
        proposed_by_interaction = {
            assessment.interaction_id: assessment for assessment in proposed.assessments
        }
        assessments = [
            self._assess(
                scan_id,
                interaction,
                proposed_by_interaction.get(interaction.id),
            )
            for interaction in interactions
            if interaction.user_facing
        ]
        return Article50AnalysisResult(assessments=assessments)

    def _assess(
        self,
        scan_id: str,
        interaction: AIInteractionFlow,
        proposed: TransparencyAssessment | None,
    ) -> TransparencyAssessment:
        relevant = self.disclosure.relevant_ui_files(scan_id, interaction)
        inspected_files = [item["file"] for item in relevant]
        candidates = self.disclosure.find_disclosure_candidates(scan_id, interaction.id)
        ambiguous = self.disclosure.find_ambiguous_context(scan_id, interaction)
        dynamic_context = self.disclosure.has_dynamic_disclosure_context(scan_id, interaction)
        complete = _has_complete_interaction_evidence(interaction)

        disclosure_candidate = candidates[0] if candidates else None
        candidate_needs_review = bool(
            disclosure_candidate
            and disclosure_candidate["file"].casefold().endswith(".json")
        )

        if disclosure_candidate and not candidate_needs_review:
            status = ReadinessStatus.PASS
            detected: bool | None = True
            explanation = (
                "A clear AI disclosure was found in the user-facing interaction context."
            )
            confidence = min(0.98, max(0.9, interaction.confidence))
        elif (
            disclosure_candidate
            or ambiguous
            or dynamic_context
            or not complete
            or not inspected_files
        ):
            status = ReadinessStatus.NEEDS_REVIEW
            detected = None
            explanation = _review_explanation(
                has_candidate=disclosure_candidate is not None,
                has_ambiguous_context=bool(ambiguous),
                has_dynamic_context=dynamic_context,
                has_frontend=bool(inspected_files),
            )
            confidence = min(0.74, max(0.5, interaction.confidence - 0.15))
        else:
            status = ReadinessStatus.ACTION_REQUIRED
            detected = False
            explanation = (
                "A direct user-facing AI interaction was detected, but no clear transparency "
                "disclosure was found in the relevant interface."
            )
            confidence = min(0.95, max(0.75, interaction.confidence))

        evidence = list(interaction.evidence)
        frontend_evidence = next(
            (
                item
                for item in interaction.evidence
                if item.file == interaction.frontend_entrypoint
                and item.type == EvidenceType.USER_INTERACTION
            ),
            None,
        )
        if frontend_evidence is not None:
            evidence.append(frontend_evidence.model_copy(update={"type": EvidenceType.UI_CONTEXT}))
        if disclosure_candidate is not None:
            disclosure_evidence = Evidence(
                file=disclosure_candidate["file"],
                line=disclosure_candidate["line"],
                snippet=disclosure_candidate["snippet"],
                type=EvidenceType.DISCLOSURE,
            )
            canonical = self.evidence.canonicalize(scan_id, disclosure_evidence)
            if canonical is not None:
                evidence.append(canonical)
        evidence = _unique_evidence(evidence)

        # Agent output can nominate a supported candidate, but it cannot manufacture a PASS or an
        # absence. Deterministic evidence remains the authority at the API boundary.
        if proposed is not None and proposed.status == status and disclosure_candidate is not None:
            proposed_text = (proposed.disclosure_text or "").casefold()
            matching = next(
                (
                    item
                    for item in candidates
                    if item["text"].casefold() == proposed_text
                    and item["file"] == proposed.disclosure_file
                    and item["line"] == proposed.disclosure_line
                ),
                None,
            )
            if matching is not None:
                disclosure_candidate = matching

        return TransparencyAssessment(
            interaction_id=interaction.id,
            rule_id=PRIMARY_ARTICLE50_RULE.id,
            status=status,
            disclosure_detected=detected,
            disclosure_text=(
                disclosure_candidate["text"] if disclosure_candidate is not None else None
            ),
            disclosure_file=(
                disclosure_candidate["file"] if disclosure_candidate is not None else None
            ),
            disclosure_line=(
                disclosure_candidate["line"] if disclosure_candidate is not None else None
            ),
            explanation=explanation,
            evidence=evidence,
            inspected_files=inspected_files,
            confidence=round(confidence, 2),
        )


def build_article50_findings(
    assessments: list[TransparencyAssessment],
    interactions: list[AIInteractionFlow],
) -> list[Finding]:
    interactions_by_id = {interaction.id: interaction for interaction in interactions}
    findings: list[Finding] = []
    for assessment in assessments:
        if assessment.status == ReadinessStatus.PASS:
            continue
        interaction = interactions_by_id.get(assessment.interaction_id)
        if assessment.status == ReadinessStatus.ACTION_REQUIRED:
            title = "Missing AI interaction disclosure"
        else:
            title = "AI interaction disclosure needs review"
        affected_files = assessment.inspected_files
        if not affected_files and interaction and interaction.frontend_entrypoint:
            affected_files = [interaction.frontend_entrypoint]
        findings.append(
            Finding(
                id=f"article50-{assessment.interaction_id}",
                rule=assessment.rule_id,
                severity="MEDIUM",
                title=title,
                explanation=assessment.explanation,
                affected_files=affected_files,
                evidence=assessment.evidence,
                confidence=assessment.confidence,
                status=assessment.status,
            )
        )
    return findings


def _has_complete_interaction_evidence(interaction: AIInteractionFlow) -> bool:
    evidence_types = {item.type for item in interaction.evidence}
    required_evidence = {
        EvidenceType.USER_INTERACTION,
        EvidenceType.API_ROUTE,
        EvidenceType.MODEL_CALL,
    }
    return bool(
        interaction.user_facing
        and interaction.frontend_entrypoint
        and interaction.api_endpoint
        and interaction.backend_handler
        and interaction.ai_provider
        and interaction.confidence >= 0.75
        and required_evidence <= evidence_types
    )


def _review_explanation(
    *,
    has_candidate: bool,
    has_ambiguous_context: bool,
    has_dynamic_context: bool,
    has_frontend: bool,
) -> str:
    if has_candidate:
        return (
            "AI-related disclosure text was found, but its visibility in the interaction context "
            "could not be confirmed automatically. Manual review is recommended."
        )
    if has_ambiguous_context:
        return (
            "The interface uses assistant-like wording, but it does not clearly state that AI is "
            "involved. Manual review is recommended."
        )
    if has_dynamic_context:
        return (
            "The interface may inject relevant text dynamically, so disclosure visibility "
            "could not "
            "be confirmed from static source evidence. Manual review is recommended."
        )
    if not has_frontend:
        return (
            "The user-facing interface could not be identified reliably, so disclosure readiness "
            "requires manual review."
        )
    return (
        "The interaction evidence is incomplete, so AI disclosure readiness requires manual review."
    )

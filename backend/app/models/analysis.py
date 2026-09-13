from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ScanStatus(StrEnum):
    PENDING = "PENDING"
    CLONING = "CLONING"
    ANALYZING = "ANALYZING"
    COMPLETED = "COMPLETED"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    PASS = "PASS"
    FAILED = "FAILED"


class ReadinessStatus(StrEnum):
    PASS = "PASS"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class PatchStatus(StrEnum):
    DRAFT = "DRAFT"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    APPLYING = "APPLYING"
    APPLIED = "APPLIED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class VerificationStatus(StrEnum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class FindingResolution(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class EvidenceType(StrEnum):
    AI_USAGE = "AI_USAGE"
    USER_INTERACTION = "USER_INTERACTION"
    API_ROUTE = "API_ROUTE"
    BACKEND_HANDLER = "BACKEND_HANDLER"
    MODEL_CALL = "MODEL_CALL"
    MODEL_CONFIGURATION = "MODEL_CONFIGURATION"
    DISCLOSURE = "DISCLOSURE"
    DISCLOSURE_ABSENCE = "DISCLOSURE_ABSENCE"
    UI_CONTEXT = "UI_CONTEXT"


class Evidence(BaseModel):
    file: str
    line: int | None = None
    snippet: str
    type: EvidenceType


class Finding(BaseModel):
    id: str
    rule: str
    severity: str
    title: str
    explanation: str
    evidence: list[Evidence]
    affected_files: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    status: ReadinessStatus = ReadinessStatus.NEEDS_REVIEW
    remediation_available: bool = False
    patch_proposal_id: str | None = None
    resolution: FindingResolution = FindingResolution.OPEN


class Article50Rule(BaseModel):
    id: str
    title: str
    description: str
    source_url: str
    source_reference: str


class TransparencyAssessment(BaseModel):
    interaction_id: str
    rule_id: str
    status: ReadinessStatus
    disclosure_detected: bool | None
    disclosure_text: str | None = None
    disclosure_file: str | None = None
    disclosure_line: int | None = None
    explanation: str
    evidence: list[Evidence] = Field(default_factory=list)
    inspected_files: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class Article50AnalysisResult(BaseModel):
    assessments: list[TransparencyAssessment] = Field(default_factory=list)


class RemediationPlan(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    rationale: str = Field(min_length=1, max_length=2000)
    disclosure_text: str = Field(min_length=1, max_length=500)
    affected_files: list[str] = Field(min_length=1)
    unified_diff: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class PatchProposal(BaseModel):
    id: str
    scan_id: str
    finding_id: str
    status: PatchStatus
    title: str = Field(min_length=1, max_length=160)
    rationale: str = Field(min_length=1, max_length=2000)
    affected_files: list[str] = Field(min_length=1)
    disclosure_text: str | None = None
    unified_diff: str = Field(min_length=1)
    original_snippets: list[Evidence] = Field(default_factory=list)
    proposed_snippets: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime
    approved_at: datetime | None = None
    applied_at: datetime | None = None
    verified_at: datetime | None = None
    modified_files: list[str] = Field(default_factory=list)
    rejected_at: datetime | None = None
    rejection_reason: str | None = Field(default=None, max_length=500)


class VerificationResult(BaseModel):
    id: str
    patch_id: str
    scan_id: str
    finding_id: str
    status: VerificationStatus
    previous_readiness_status: ReadinessStatus
    new_readiness_status: ReadinessStatus
    disclosure_detected: bool | None
    explanation: str
    evidence: list[Evidence] = Field(default_factory=list)
    verified_at: datetime


class PatchApplyResponse(BaseModel):
    patch_id: str
    patch_status: PatchStatus
    verification: VerificationResult


class AIUsage(BaseModel):
    provider: str | None = None
    sdk: str | None = None
    model: str | None = None
    file: str
    line: int | None = None
    purpose: str | None = None
    evidence: list[Evidence]
    confidence: float = Field(ge=0.0, le=1.0)


class AIInteractionFlow(BaseModel):
    id: str
    name: str
    user_facing: bool
    frontend_entrypoint: str | None = None
    api_endpoint: str | None = None
    backend_handler: str | None = None
    ai_provider: str | None = None
    ai_model: str | None = None
    flow_summary: str
    evidence: list[Evidence]
    confidence: float = Field(ge=0.0, le=1.0)


class AIInvestigationResult(BaseModel):
    ai_usages: list[AIUsage] = Field(default_factory=list)
    ai_interactions: list[AIInteractionFlow] = Field(default_factory=list)


class SourceSnapshot(BaseModel):
    file: str
    content: str
    sha256: str


class RemediationContext(BaseModel):
    scan_id: str
    finding: Finding
    assessment: TransparencyAssessment
    interaction: AIInteractionFlow
    source_files: list[SourceSnapshot]


class RepositoryAnalysis(BaseModel):
    id: str
    repository_url: str
    status: ScanStatus
    frameworks: list[str]
    findings: list[Finding]
    ai_usages: list[AIUsage] = Field(default_factory=list)
    ai_interactions: list[AIInteractionFlow] = Field(default_factory=list)
    article50_assessments: list[TransparencyAssessment] = Field(default_factory=list)

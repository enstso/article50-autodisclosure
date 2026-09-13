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


class RepositoryAnalysis(BaseModel):
    id: str
    repository_url: str
    status: ScanStatus
    frameworks: list[str]
    findings: list[Finding]
    ai_usages: list[AIUsage] = Field(default_factory=list)
    ai_interactions: list[AIInteractionFlow] = Field(default_factory=list)
    article50_assessments: list[TransparencyAssessment] = Field(default_factory=list)

from enum import StrEnum

from pydantic import BaseModel, Field


class ScanStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    PASS = "PASS"
    FAILED = "FAILED"


class EvidenceType(StrEnum):
    AI_USAGE = "AI_USAGE"
    USER_INTERACTION = "USER_INTERACTION"
    DISCLOSURE = "DISCLOSURE"


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


class RepositoryAnalysis(BaseModel):
    id: str
    repository_url: str
    status: ScanStatus
    frameworks: list[str]
    findings: list[Finding]


from pydantic import BaseModel, Field

from app.models.analysis import AIInteractionFlow, AIUsage, ScanStatus


class RepositorySummary(BaseModel):
    languages: list[str]
    frameworks: list[str]
    architecture_summary: str
    important_files: list[str]
    potential_ai_integrations: list[str] = Field(default_factory=list)


class Scan(BaseModel):
    id: str
    repository_url: str
    status: ScanStatus = ScanStatus.PENDING
    summary: RepositorySummary | None = None
    ai_usages: list[AIUsage] = Field(default_factory=list)
    ai_interactions: list[AIInteractionFlow] = Field(default_factory=list)
    error: str | None = None
    events: list[str] = Field(default_factory=list)


class ScanCreateRequest(BaseModel):
    repository_url: str = Field(min_length=1, max_length=2048)

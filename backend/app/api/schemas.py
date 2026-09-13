from typing import Literal

from pydantic import BaseModel, Field

from app.models import ModelMode


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    model_mode: ModelMode
    model_provider: str


class PatchRejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)

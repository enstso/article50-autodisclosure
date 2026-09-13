from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str


class PatchRejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)

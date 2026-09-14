from fastapi import APIRouter, Depends

from app.api.schemas import HealthResponse
from app.core.config import Settings, get_settings
from app.models import ModelMode

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    mock_enabled = settings.use_mock_model
    return HealthResponse(
        status="ok",
        service="article50-autodisclosure-api",
        model_mode=ModelMode.DEMO if mock_enabled else ModelMode.LIVE,
        model_provider="Mock model" if mock_enabled else "Amazon Bedrock",
    )

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.use_mock_model:
        logger.info("Demo mode enabled")
        logger.info("Mock model enabled")
    else:
        logger.info("Amazon Bedrock mode enabled")
        logger.info("Region: %s", settings.aws_region)
        logger.info("Model: %s", settings.bedrock_model_id)
    yield

app = FastAPI(
    title="Article 50 AutoDisclosure API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

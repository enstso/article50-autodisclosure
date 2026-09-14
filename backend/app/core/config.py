from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "global.anthropic.claude-sonnet-4-6"
    use_mock_model: bool = False
    workspace_path: Path = Path("./workspace")
    max_repository_size_mb: int = Field(default=50, gt=0)
    max_file_size_kb: int = Field(default=250, gt=0)
    max_patch_lines: int = Field(default=120, gt=0)
    frontend_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])


@lru_cache
def get_settings() -> Settings:
    return Settings()

from functools import lru_cache
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "AgentForge"
    app_env: str = "development"
    secret_key: str = "dev-secret-key-change-in-production-min-32"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # Database
    database_url: str = (
        "postgresql+asyncpg://agentforge:password@localhost:5432/agentforge"
    )
    database_sync_url: str = (
        "postgresql+psycopg://agentforge:password@localhost:5432/agentforge"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # AWS
    aws_region: str = "us-east-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_session_token: Optional[str] = None

    # Bedrock
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    bedrock_fast_model_id: str = "anthropic.claude-3-5-haiku-20241022-v1:0"
    bedrock_max_tokens: int = 8192
    bedrock_temperature: float = 0.1

    # S3
    s3_bucket_name: str = "agentforge-artifacts"

    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    
    # Frontend
    frontend_url: str = "http://localhost:3000"

    def get_cors_origins_list(self) -> list[str]:
        """Convert CORS origins string to list"""
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return [self.cors_origins]


@lru_cache()
def get_settings() -> Settings:
    return Settings()

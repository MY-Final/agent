from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量或 .env 文件加载应用配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    app_name: str = Field(default="投标分析 Agent 后端", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database_url: str = Field(alias="DATABASE_URL")
    database_echo: bool = Field(default=False, alias="DATABASE_ECHO")
    redis_url: str = Field(alias="REDIS_URL")
    redis_connect_timeout_seconds: float = Field(
        default=3.0,
        gt=0,
        le=60,
        alias="REDIS_CONNECT_TIMEOUT_SECONDS",
    )

    minio_endpoint: str = Field(alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(alias="MINIO_SECRET_KEY")
    minio_bucket: str = Field(default="tender-files", alias="MINIO_BUCKET")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")
    minio_region: str = Field(default="us-east-1", alias="MINIO_REGION")
    minio_presigned_expiry_seconds: int = Field(
        default=3600,
        ge=1,
        le=604800,
        alias="MINIO_PRESIGNED_EXPIRY_SECONDS",
    )

    cors_origins: list[str] = Field(default_factory=lambda: ["*"], alias="CORS_ORIGINS")
    max_upload_size_bytes: int = Field(
        default=500 * 1024 * 1024,
        gt=0,
        alias="MAX_UPLOAD_SIZE_BYTES",
    )

    @field_validator("minio_endpoint")
    @classmethod
    def normalize_minio_endpoint(cls, value: str) -> str:
        return value.removeprefix("http://").removeprefix("https://").rstrip("/")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def minio_url(self) -> str:
        scheme = "https" if self.minio_secure else "http"
        return f"{scheme}://{self.minio_endpoint}"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()

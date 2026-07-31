from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

from app.core.runtime_config import (
    build_database_url,
    build_redis_url,
    load_runtime_config,
)


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

    llm_api_key: SecretStr | None = Field(default=None, alias="LLM_API_KEY")
    llm_base_url: str | None = Field(default=None, alias="LLM_BASE_URL")
    llm_model_name: str = Field(default="gpt-4.1-mini", alias="LLM_MODEL_NAME")
    llm_timeout_seconds: float = Field(
        default=120.0,
        gt=0,
        le=600,
        alias="LLM_TIMEOUT_SECONDS",
    )

    pdf_text_min_chars: int = Field(
        default=300,
        ge=1,
        alias="PDF_TEXT_MIN_CHARS",
    )
    ocr_language: str = Field(default="ch", alias="OCR_LANGUAGE")
    ocr_render_scale: float = Field(
        default=2.0,
        ge=1.0,
        le=4.0,
        alias="OCR_RENDER_SCALE",
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

    @field_validator("llm_api_key", "llm_base_url", mode="before")
    @classmethod
    def empty_value_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("llm_base_url")
    @classmethod
    def normalize_llm_base_url(cls, value: str | None) -> str | None:
        return value.rstrip("/") if value else None

    @property
    def minio_url(self) -> str:
        scheme = "https" if self.minio_secure else "http"
        return f"{scheme}://{self.minio_endpoint}"

    @property
    def langgraph_database_url(self) -> str:
        """将 SQLAlchemy asyncpg 地址转换为 LangGraph checkpointer 地址。"""

        url = make_url(self.database_url)
        if url.drivername == "postgresql+asyncpg":
            url = url.set(drivername="postgresql")
        return url.render_as_string(hide_password=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()

# 桌面端系统设置保存的运行时配置优先于 .env。
# 引擎等基础设施对象都在导入时基于 settings 创建，因此这里在导入阶段统一覆盖。
_RUNTIME = load_runtime_config()
if _RUNTIME:
    _postgres = _RUNTIME.get("postgres") or {}
    if _postgres.get("host") and _postgres.get("database"):
        settings.database_url = build_database_url(_postgres)
    _redis = _RUNTIME.get("redis") or {}
    if _redis.get("host"):
        settings.redis_url = build_redis_url(_redis)
    _minio = _RUNTIME.get("minio") or {}
    if _minio.get("endpoint"):
        settings.minio_endpoint = str(_minio["endpoint"])
        settings.minio_access_key = str(
            _minio.get("access_key") or settings.minio_access_key
        )
        settings.minio_secret_key = str(
            _minio.get("secret_key") or settings.minio_secret_key
        )
        settings.minio_bucket = str(_minio.get("bucket") or settings.minio_bucket)
        settings.minio_secure = bool(_minio.get("secure", settings.minio_secure))

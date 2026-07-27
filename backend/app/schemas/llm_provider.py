import uuid
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

from app.models.llm_provider import LLMProvider
from app.utils.secrets import mask_api_key


ProviderType = Literal["openai_compatible"]


def _normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("大模型服务地址必须是有效的 HTTP 或 HTTPS URL")
    return normalized


class LLMProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    provider_type: ProviderType = "openai_compatible"
    base_url: str = Field(min_length=1, max_length=2048)
    api_key: SecretStr
    default_model: str = Field(min_length=1, max_length=255)
    timeout_seconds: int = Field(default=120, gt=0, le=600)
    is_default: bool = False
    is_enabled: bool = True
    extra_config: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "default_model")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("该字段不能为空")
        return normalized

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        return _normalize_base_url(value)

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value().strip()
        if not secret:
            raise ValueError("API Key 不能为空")
        return SecretStr(secret)

    @model_validator(mode="after")
    def validate_default_state(self) -> "LLMProviderCreate":
        if self.is_default and not self.is_enabled:
            raise ValueError("禁用的提供商不能设为默认提供商")
        return self


class LLMProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    provider_type: ProviderType | None = None
    base_url: str | None = Field(default=None, min_length=1, max_length=2048)
    api_key: SecretStr | None = None
    default_model: str | None = Field(default=None, min_length=1, max_length=255)
    timeout_seconds: int | None = Field(default=None, gt=0, le=600)
    is_default: bool | None = None
    is_enabled: bool | None = None
    extra_config: dict[str, Any] | None = None

    @field_validator("name", "default_model")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("该字段不能为空")
        return normalized

    @field_validator("base_url")
    @classmethod
    def validate_optional_base_url(cls, value: str | None) -> str | None:
        return _normalize_base_url(value) if value is not None else None

    @field_validator("api_key")
    @classmethod
    def normalize_optional_api_key(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        secret = value.get_secret_value().strip()
        return SecretStr(secret) if secret else None

    @model_validator(mode="after")
    def validate_update(self) -> "LLMProviderUpdate":
        nullable_fields = {
            "name": "显示名称",
            "provider_type": "提供商类型",
            "base_url": "服务地址",
            "default_model": "默认模型",
            "timeout_seconds": "超时时间",
            "is_default": "默认状态",
            "is_enabled": "启用状态",
            "extra_config": "扩展配置",
        }
        for field, label in nullable_fields.items():
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{label}不能为 null")
        if self.is_default is True and self.is_enabled is False:
            raise ValueError("禁用的提供商不能设为默认提供商")
        return self


class LLMProviderRead(BaseModel):
    id: uuid.UUID
    name: str
    provider_type: str
    base_url: str
    api_key: str
    default_model: str
    timeout_seconds: int
    is_default: bool
    is_enabled: bool
    extra_config: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: LLMProvider) -> "LLMProviderRead":
        # 绝不通过 from_attributes 直接序列化数据库中的完整密钥。
        return cls(
            id=record.id,
            name=record.name,
            provider_type=record.provider_type,
            base_url=record.base_url,
            api_key=mask_api_key(record.api_key),
            default_model=record.default_model,
            timeout_seconds=record.timeout_seconds,
            is_default=record.is_default,
            is_enabled=record.is_enabled,
            extra_config=record.extra_config,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class CurrentLLMConfigRead(BaseModel):
    source: Literal["database", "env"]
    provider_id: uuid.UUID | None
    provider_name: str | None
    provider_type: str
    base_url: str | None
    api_key: str | None
    default_model: str
    timeout_seconds: float
    extra_config: dict[str, Any]
    is_configured: bool


class LLMConnectionBase(BaseModel):
    """测试未保存配置；编辑时可通过 provider_id 复用数据库密钥。"""

    provider_id: uuid.UUID | None = None
    base_url: str = Field(min_length=1, max_length=2048)
    api_key: SecretStr | None = None
    timeout_seconds: int = Field(default=120, gt=0, le=600)

    @field_validator("base_url")
    @classmethod
    def validate_connection_base_url(cls, value: str) -> str:
        return _normalize_base_url(value)

    @field_validator("api_key")
    @classmethod
    def normalize_connection_api_key(
        cls,
        value: SecretStr | None,
    ) -> SecretStr | None:
        if value is None:
            return None
        secret = value.get_secret_value().strip()
        return SecretStr(secret) if secret else None


class LLMModelListRequest(LLMConnectionBase):
    pass


class LLMModelListRead(BaseModel):
    models: list[str]
    count: int


class LLMConnectionTestRequest(LLMConnectionBase):
    model: str = Field(min_length=1, max_length=255)

    @field_validator("model")
    @classmethod
    def normalize_test_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("测试模型不能为空")
        return normalized


class LLMConnectionTestRead(BaseModel):
    success: bool = True
    model: str
    latency_ms: int

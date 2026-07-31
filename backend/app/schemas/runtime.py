from pydantic import BaseModel, Field


class PostgresConfig(BaseModel):
    host: str = Field(default="127.0.0.1", min_length=1, max_length=255)
    port: int = Field(default=5432, ge=1, le=65535)
    user: str = Field(default="postgres", min_length=1, max_length=255)
    password: str | None = Field(default=None, max_length=512)
    database: str = Field(default="tender", min_length=1, max_length=255)


class RedisConfig(BaseModel):
    host: str = Field(default="127.0.0.1", min_length=1, max_length=255)
    port: int = Field(default=6379, ge=1, le=65535)
    password: str | None = Field(default=None, max_length=512)
    db: int = Field(default=0, ge=0, le=15)


class MinioConfig(BaseModel):
    endpoint: str = Field(default="localhost:9000", min_length=1, max_length=255)
    access_key: str = Field(default="minioadmin", min_length=1, max_length=255)
    secret_key: str | None = Field(default=None, max_length=512)
    bucket: str = Field(default="tender-files", min_length=1, max_length=255)
    secure: bool = False


class RuntimeSettingsInput(BaseModel):
    postgres: PostgresConfig
    redis: RedisConfig
    minio: MinioConfig


class ComponentHealth(BaseModel):
    ok: bool
    message: str | None = None


class RuntimeTestResult(BaseModel):
    postgres: ComponentHealth
    redis: ComponentHealth
    minio: ComponentHealth


class RuntimeSettingsRead(BaseModel):
    postgres: PostgresConfig
    redis: RedisConfig
    minio: MinioConfig
    health: RuntimeTestResult
    config_file: str

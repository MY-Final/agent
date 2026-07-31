import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.parse_template import ParseTemplate as ParseTemplateORM
from app.schemas.skills.parse import ParseTemplate, SectionDefinition


class ParseTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    version: str = Field(default="v1", min_length=1, max_length=32)
    sections: list[SectionDefinition]
    is_default: bool = False

    @model_validator(mode="after")
    def require_sections(self) -> "ParseTemplateCreate":
        if not self.sections:
            raise ValueError("模板至少需要一个 section")
        return self


class ParseTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    version: str | None = Field(default=None, min_length=1, max_length=32)
    sections: list[SectionDefinition] | None = None
    is_default: bool | None = None

    @model_validator(mode="after")
    def reject_empty_sections(self) -> "ParseTemplateUpdate":
        if self.sections is not None and not self.sections:
            raise ValueError("模板至少需要一个 section")
        return self


class ParseTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    version: str
    sections: list[SectionDefinition]
    is_default: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, record: ParseTemplateORM) -> "ParseTemplateRead":
        return cls(
            id=record.id,
            name=record.name,
            description=record.description,
            version=record.version,
            sections=[
                SectionDefinition.model_validate(item) for item in record.sections
            ],
            is_default=record.is_default,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )


class TemplateSuggestionInput(BaseModel):
    description: str = Field(min_length=1, max_length=2000)
    reference_text: str | None = Field(default=None, max_length=20000)


class TemplateSuggestion(BaseModel):
    """LLM 根据自然语言描述生成的模板建议，人工确认后落库为正式模板。"""

    suggested_name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    sections: list[SectionDefinition] = Field(min_length=1)


def template_to_schema(template: ParseTemplateORM) -> ParseTemplate:
    """把 ORM 模板转换为解析技能消费的 ParseTemplate 外壳。"""

    return ParseTemplate(
        version=template.version,
        sections=[
            SectionDefinition.model_validate(item) for item in template.sections
        ],
    )

import enum
import logging
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.models.parse_result import ParseResultStatus, TaskParseResult


logger = logging.getLogger(__name__)


class QualificationItem(BaseModel):
    """资格要求行的稳定契约结构，供确定性匹配引擎消费。"""

    model_config = ConfigDict(extra="forbid")

    category: str = Field(description="资质、业绩、人员、财务或其他")
    description: str
    is_mandatory: bool = True
    original_text: str | None = None


class FieldType(str, enum.Enum):
    """模板中单个字段/列允许的标量类型。"""

    TEXT = "text"
    NUMBER = "number"
    MONEY = "money"
    DATE = "date"
    BOOLEAN = "boolean"


class SectionKind(str, enum.Enum):
    """Section 的渲染方式，前端按 kind 分发到通用渲染器。"""

    GRID = "grid"
    TABLE = "table"
    KEY_VALUE = "key_value"
    LIST = "list"


class SectionTone(str, enum.Enum):
    """Section 的语义色，用于前端标注条与图标着色。"""

    DEFAULT = "default"
    PRIMARY = "primary"
    WARNING = "warning"
    DANGER = "danger"
    SUCCESS = "success"
    INFO = "info"


class ColumnVariant(str, enum.Enum):
    """表格列在通用渲染器中的展示变体。"""

    TEXT = "text"
    MUTED = "muted"
    STACK = "stack"
    TAG = "tag"


class FieldDefinition(BaseModel):
    """grid 类型 section 中的字段定义。"""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    type: FieldType = FieldType.TEXT
    required: bool = False


class ColumnDefinition(BaseModel):
    """table 类型 section 中的列定义。"""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    type: FieldType = FieldType.TEXT
    required: bool = False
    variant: ColumnVariant = ColumnVariant.TEXT
    secondary_key: str | None = None
    secondary_prefix: str | None = None
    truthy_label: str | None = None
    falsy_label: str | None = None
    truthy_tag: str | None = None
    falsy_tag: str | None = None
    width: int | None = Field(default=None, gt=0)
    min_width: int | None = Field(default=None, gt=0)


class SectionDefinition(BaseModel):
    """模板中的一个渲染单元。"""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    subtitle: str | None = None
    kind: SectionKind
    tone: SectionTone = SectionTone.DEFAULT
    icon: str | None = None
    fields: list[FieldDefinition] = Field(default_factory=list)
    columns: list[ColumnDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_kind_consistency(self) -> "SectionDefinition":
        if self.kind == SectionKind.GRID and not self.fields:
            raise ValueError("grid 类型 section 必须包含 fields")
        if self.kind == SectionKind.TABLE and not self.columns:
            raise ValueError("table 类型 section 必须包含 columns")
        if self.kind == SectionKind.GRID and self.columns:
            raise ValueError("grid 类型 section 不应包含 columns")
        if self.kind == SectionKind.TABLE and self.fields:
            raise ValueError("table 类型 section 不应包含 fields")
        if self.kind in {SectionKind.KEY_VALUE, SectionKind.LIST} and (
            self.fields or self.columns
        ):
            raise ValueError("key_value/list 类型 section 不应包含 fields 或 columns")
        return self


class ParseTemplate(BaseModel):
    """一次解析的字段模板：固定外壳中的元数据部分，前端据此渲染。"""

    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1)
    sections: list[SectionDefinition]

    @model_validator(mode="after")
    def validate_unique_keys(self) -> "ParseTemplate":
        section_ids = [section.id for section in self.sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("模板中存在重复的 section id")
        for section in self.sections:
            keys = [field.key for field in section.fields] + [
                column.key for column in section.columns
            ]
            if len(keys) != len(set(keys)):
                raise ValueError(f"section {section.id} 中存在重复的字段 key")
        return self


def _expect_scalar(value: Any, field_type: FieldType) -> bool:
    if field_type == FieldType.NUMBER:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if field_type == FieldType.BOOLEAN:
        return isinstance(value, bool)
    return isinstance(value, str)


def _table_property_keys(section: SectionDefinition) -> list[str]:
    """table section 的全部数据键：列定义 + stack 变体引用的副键。"""

    keys = [column.key for column in section.columns]
    for column in section.columns:
        if column.variant == ColumnVariant.STACK and column.secondary_key:
            keys.append(column.secondary_key)
    return keys


def _table_field_types(section: SectionDefinition) -> dict[str, FieldType]:
    """列定义与 stack 副键的数据键 -> 标量类型映射。"""

    types = {column.key: column.type for column in section.columns}
    for column in section.columns:
        if column.variant == ColumnVariant.STACK and column.secondary_key:
            types[column.secondary_key] = FieldType.TEXT
    return types


def validate_data_against_template(
    template: ParseTemplate,
    data: dict[str, Any],
) -> None:
    """按模板校验 data；类型或键不符合时抛出 ValueError。"""

    if not isinstance(data, dict):
        raise ValueError("data 必须是对象")

    for section in template.sections:
        value = data.get(section.id)
        if section.kind == SectionKind.GRID:
            _validate_grid_data(section, value)
        elif section.kind == SectionKind.TABLE:
            _validate_table_data(section, value)
        elif section.kind == SectionKind.KEY_VALUE:
            _validate_key_value_data(section, value)
        else:
            _validate_list_data(section, value)


def _validate_grid_data(section: SectionDefinition, value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"section {section.title} 必须是对象")
    keys = {field.key for field in section.fields}
    if set(value) - keys:
        raise ValueError(f"section {section.title} 包含模板之外的字段")
    for field in section.fields:
        if field.key not in value:
            raise ValueError(f"section {section.title} 缺少字段 {field.label}")
        item = value[field.key]
        if item is not None and not _expect_scalar(item, field.type):
            raise ValueError(
                f"section {section.title} 的字段 {field.label} 类型应为 {field.type.value}"
            )


def _validate_table_data(section: SectionDefinition, value: Any) -> None:
    if not isinstance(value, list):
        raise ValueError(f"section {section.title} 必须是数组")
    property_keys = set(_table_property_keys(section))
    required_keys = {
        column.key for column in section.columns if column.required
    }
    field_types = _table_field_types(section)
    for row in value:
        if not isinstance(row, dict):
            raise ValueError(f"section {section.title} 的每一行必须是对象")
        if set(row) - property_keys:
            raise ValueError(f"section {section.title} 存在模板之外的列")
        for key, item in row.items():
            if item is None:
                if key in required_keys:
                    raise ValueError(f"section {section.title} 的必填列不能为空：{key}")
                continue
            field_type = field_types.get(key)
            if field_type is None:
                raise ValueError(f"section {section.title} 的列 {key} 缺少类型定义")
            if not _expect_scalar(item, field_type):
                raise ValueError(
                    f"section {section.title} 的列 {key} 类型应为 {field_type.value}"
                )


def _validate_key_value_data(section: SectionDefinition, value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"section {section.title} 必须是对象")
    for key, item in value.items():
        if item is not None and not isinstance(item, (str, int, float, bool)):
            raise ValueError(f"section {section.title} 的键值 {key} 必须是标量")


def _validate_list_data(section: SectionDefinition, value: Any) -> None:
    if not isinstance(value, list):
        raise ValueError(f"section {section.title} 必须是数组")
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"section {section.title} 的条目必须是字符串")


class ParseResult(BaseModel):
    """标书解析的固定外壳：template（元数据）+ data（值）。"""

    model_config = ConfigDict(extra="forbid")

    template: ParseTemplate
    data: dict[str, Any]
    raw_summary: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_data(self) -> "ParseResult":
        validate_data_against_template(self.template, self.data)
        return self

    def field_value(self, section_id: str, field_key: str) -> Any:
        section_data = self.data.get(section_id)
        if isinstance(section_data, dict):
            return section_data.get(field_key)
        return None

    @property
    def project_name(self) -> str | None:
        value = self.field_value("overview", "project_name")
        return value if isinstance(value, str) else None

    @property
    def project_code(self) -> str | None:
        value = self.field_value("overview", "project_code")
        return value if isinstance(value, str) else None

    @property
    def budget(self) -> str | None:
        value = self.field_value("overview", "budget")
        return value if isinstance(value, str) else None

    @property
    def qualifications(self) -> list[QualificationItem]:
        """契约字段：匹配引擎依赖的资格要求行，由模板数据转换而来。"""

        rows = self.data.get("qualifications")
        if not isinstance(rows, list):
            return []
        return [QualificationItem.model_validate(row) for row in rows]


class ParseInput(BaseModel):
    """独立 Skill 调试入口，一次必须且只能选择一种文件定位方式。"""

    task_id: uuid.UUID | None = Field(
        default=None,
        description="解析该任务下全部支持的标书文件",
    )
    file_id: uuid.UUID | None = Field(
        default=None,
        description="解析 task_files 中的单个文件",
    )
    object_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=1024,
        description="直接解析 MinIO object_key，适合独立调试",
    )

    @model_validator(mode="after")
    def validate_single_source(self) -> "ParseInput":
        selected = sum(
            value is not None
            for value in (self.task_id, self.file_id, self.object_key)
        )
        if selected != 1:
            raise ValueError("task_id、file_id、object_key 必须且只能填写一个")
        return self


class ParseResultRead(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID | None
    file_id: uuid.UUID | None
    source_object_keys: list[str]
    template_id: uuid.UUID | None
    template_version: str | None
    is_rejected: bool
    reject_reason: str | None
    status: ParseResultStatus
    result: ParseResult | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm_record(cls, record: TaskParseResult) -> "ParseResultRead":
        parsed_result: ParseResult | None = None
        if record.result_json is not None:
            try:
                parsed_result = ParseResult.model_validate(record.result_json)
            except ValidationError:
                # 旧模板数据不再兼容时，仅返回空结果而不是让接口报错。
                logger.warning(
                    "解析结果与当前模板不兼容，parse_result_id=%s",
                    record.id,
                )
        return cls(
            id=record.id,
            task_id=record.task_id,
            file_id=record.file_id,
            source_object_keys=record.source_object_keys,
            template_id=record.template_id,
            template_version=record.template_version,
            is_rejected=record.is_rejected,
            reject_reason=record.reject_reason,
            status=record.status,
            result=parsed_result,
            error_message=record.error_message,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

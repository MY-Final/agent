from typing import Any

from app.skills.prompt_loader import PROMPTS
from app.schemas.skills.parse import (
    ColumnDefinition,
    ColumnVariant,
    FieldDefinition,
    FieldType,
    ParseTemplate,
    SectionDefinition,
    SectionKind,
    SectionTone,
)


SEED_PARSE_TEMPLATE = ParseTemplate(
    version="v1",
    sections=[
        SectionDefinition(
            id="overview",
            title="项目概览",
            subtitle="招标文件的核心信息摘要",
            kind=SectionKind.GRID,
            tone=SectionTone.PRIMARY,
            icon="Memo",
            fields=[
                FieldDefinition(
                    key="project_name",
                    label="项目名称",
                    type=FieldType.TEXT,
                    required=True,
                ),
                FieldDefinition(key="project_code", label="项目编号", type=FieldType.TEXT),
                FieldDefinition(key="purchaser", label="采购人", type=FieldType.TEXT),
                FieldDefinition(key="budget", label="预算金额", type=FieldType.MONEY),
                FieldDefinition(key="location", label="项目地点", type=FieldType.TEXT),
                FieldDefinition(key="duration", label="项目工期", type=FieldType.TEXT),
            ],
        ),
        SectionDefinition(
            id="qualifications",
            title="资格要求",
            subtitle="资质、业绩、人员、财务和其他准入条件",
            kind=SectionKind.TABLE,
            tone=SectionTone.PRIMARY,
            icon="Collection",
            columns=[
                ColumnDefinition(
                    key="category",
                    label="类别",
                    type=FieldType.TEXT,
                    required=True,
                    width=110,
                ),
                ColumnDefinition(
                    key="description",
                    label="要求",
                    type=FieldType.TEXT,
                    required=True,
                    variant=ColumnVariant.STACK,
                    secondary_key="original_text",
                    secondary_prefix="原文",
                    min_width=320,
                ),
                ColumnDefinition(
                    key="is_mandatory",
                    label="性质",
                    type=FieldType.BOOLEAN,
                    variant=ColumnVariant.TAG,
                    truthy_label="强制",
                    falsy_label="一般",
                    truthy_tag="danger",
                    falsy_tag="info",
                    width=100,
                ),
            ],
        ),
        SectionDefinition(
            id="scoring_method",
            title="评分办法",
            subtitle="商务、技术和价格等评分信息",
            kind=SectionKind.KEY_VALUE,
            tone=SectionTone.INFO,
            icon="Tickets",
        ),
        SectionDefinition(
            id="key_dates",
            title="关键时间",
            subtitle="报名、投标截止和开标等节点",
            kind=SectionKind.KEY_VALUE,
            tone=SectionTone.WARNING,
            icon="Calendar",
        ),
        SectionDefinition(
            id="disqualification_items",
            title="废标条款",
            subtitle="需要优先核验的否决条件",
            kind=SectionKind.LIST,
            tone=SectionTone.DANGER,
            icon="WarningFilled",
        ),
        SectionDefinition(
            id="other_key_points",
            title="其他要点",
            subtitle="值得关注的补充信息",
            kind=SectionKind.LIST,
            tone=SectionTone.DEFAULT,
            icon="List",
        ),
    ],
)


def build_suggestion_prompt(
    description: str,
    reference_text: str | None,
) -> str:
    """把自然语言需求组装成模板建议的用户消息（正文模板见 prompts/）。"""

    reference_block = ""
    if reference_text and reference_text.strip():
        reference_block = (
            "参考原文（从中提炼字段会更准确）：\n"
            + reference_text.strip()[:20000]
        )
    return PROMPTS["suggest_user"].render(
        description=description,
        reference_block=reference_block,
    )


def with_core_contract(
    sections: list[SectionDefinition],
) -> list[SectionDefinition]:
    """保证建议模板始终包含匹配引擎依赖的资格要求表格。

    以内置 canonical 区块为准，避免 LLM 输出列结构不完整导致匹配链路断裂。
    """

    canonical = next(
        (
            section
            for section in SEED_PARSE_TEMPLATE.sections
            if section.id == "qualifications"
        ),
        None,
    )
    if canonical is None:
        return sections
    rest = [section for section in sections if section.id != "qualifications"]
    return [canonical, *rest]


_ALLOWED_SECTION_ICONS = {
    "Memo",
    "Collection",
    "Tickets",
    "Calendar",
    "WarningFilled",
    "List",
    "Document",
    "DataLine",
}
_ALLOWED_TAG_TYPES = {"primary", "success", "warning", "info", "danger"}


def sanitize_sections(
    sections: list[SectionDefinition],
) -> list[SectionDefinition]:
    """清洗 LLM 建议里的自由字段：非法图标/标签色回退为 null。"""

    cleaned: list[SectionDefinition] = []
    for section in sections:
        columns = None
        if section.columns:
            columns = [
                column.model_copy(
                    update={
                        "truthy_tag": (
                            column.truthy_tag
                            if column.truthy_tag in _ALLOWED_TAG_TYPES
                            else None
                        ),
                        "falsy_tag": (
                            column.falsy_tag
                            if column.falsy_tag in _ALLOWED_TAG_TYPES
                            else None
                        ),
                    }
                )
                for column in section.columns
            ]
        cleaned.append(
            section.model_copy(
                update={
                    "icon": (
                        section.icon if section.icon in _ALLOWED_SECTION_ICONS else None
                    ),
                    "columns": columns,
                }
            )
        )
    return cleaned


def describe_template(template: ParseTemplate) -> str:
    """把模板转成提示词里的人类可读字段清单。"""

    lines: list[str] = []
    for section in template.sections:
        if section.kind == SectionKind.GRID:
            fields = "、".join(
                f"{field.label}（{_field_type_label(field.type)}）"
                for field in section.fields
            )
            lines.append(f"- {section.title}：{fields}")
        elif section.kind == SectionKind.TABLE:
            columns = "、".join(column.label for column in section.columns)
            lines.append(f"- {section.title}（表格，每行包含：{columns}）")
        elif section.kind == SectionKind.KEY_VALUE:
            lines.append(f"- {section.title}（键值对，键为维度名，值为对应内容）")
        else:
            lines.append(f"- {section.title}（字符串列表）")
    return "\n".join(lines)


def build_extraction_schema(template: ParseTemplate) -> dict[str, Any]:
    """根据模板生成传给 LLM 的响应 JSON Schema。"""

    data_properties: dict[str, Any] = {}
    for section in template.sections:
        data_properties[section.id] = _section_schema(section)
    return {
        "type": "object",
        "properties": {
            "data": {
                "type": "object",
                "properties": data_properties,
                "required": [section.id for section in template.sections],
                "additionalProperties": False,
            },
            "raw_summary": {"type": ["string", "null"]},
            "confidence": {"type": ["number", "null"]},
        },
        "required": ["data"],
        "additionalProperties": False,
    }


def _field_type_label(field_type: FieldType) -> str:
    return {
        FieldType.TEXT: "文本",
        FieldType.NUMBER: "数字",
        FieldType.MONEY: "金额文本",
        FieldType.DATE: "日期",
        FieldType.BOOLEAN: "布尔值",
    }[field_type]


def _field_json_type(field_type: FieldType) -> str:
    if field_type == FieldType.BOOLEAN:
        return "boolean"
    if field_type == FieldType.NUMBER:
        return "number"
    return "string"


def _nullable_type(field_type: FieldType) -> list[str]:
    return [_field_json_type(field_type), "null"]


def _section_schema(section: SectionDefinition) -> dict[str, Any]:
    if section.kind == SectionKind.GRID:
        properties = {
            field.key: {"type": _nullable_type(field.type)}
            for field in section.fields
        }
        return {
            "type": "object",
            "properties": properties,
            "required": [field.key for field in section.fields],
            "additionalProperties": False,
        }
    if section.kind == SectionKind.TABLE:
        properties = {
            column.key: {"type": _nullable_type(column.type)}
            for column in section.columns
        }
        for column in section.columns:
            if column.variant == ColumnVariant.STACK and column.secondary_key:
                properties[column.secondary_key] = {"type": ["string", "null"]}
        return {
            "type": "array",
            "items": {
                "type": "object",
                "properties": properties,
                "required": [
                    column.key for column in section.columns if column.required
                ],
                "additionalProperties": False,
            },
        }
    if section.kind == SectionKind.KEY_VALUE:
        return {
            "type": "object",
            "additionalProperties": {"type": ["string", "number", "boolean", "null"]},
        }
    return {"type": "array", "items": {"type": "string"}}

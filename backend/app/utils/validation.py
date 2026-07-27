from typing import Any


SENSITIVE_FIELD_NAMES = {
    "api_key",
    "access_key",
    "secret_key",
    "password",
    "token",
}


def _sanitize_input(value: Any, *, field_name: str | None = None) -> Any:
    """清洗校验错误中的请求输入，避免错误响应回显敏感字段。"""

    if field_name and field_name.lower() in SENSITIVE_FIELD_NAMES:
        return "********"
    if isinstance(value, dict):
        return {
            key: _sanitize_input(item, field_name=str(key))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_input(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_input(item) for item in value]
    return value


def _translate_message(error_type: str, context: dict[str, Any]) -> str:
    """根据 Pydantic 错误类型生成中文提示。"""
    if error_type == "missing":
        return "该字段为必填项"
    if error_type == "string_type":
        return "该字段必须是字符串"
    if error_type == "string_too_short":
        return f"字符长度不能少于 {context.get('min_length')}"
    if error_type == "string_too_long":
        return f"字符长度不能超过 {context.get('max_length')}"
    if error_type in {"int_type", "int_parsing"}:
        return "该字段必须是整数"
    if error_type == "greater_than":
        return f"数值必须大于 {context.get('gt')}"
    if error_type == "greater_than_equal":
        return f"数值不能小于 {context.get('ge')}"
    if error_type == "less_than":
        return f"数值必须小于 {context.get('lt')}"
    if error_type == "less_than_equal":
        return f"数值不能大于 {context.get('le')}"
    if error_type == "uuid_parsing":
        return "必须填写正确的 UUID"
    if error_type == "enum":
        return "填写的值不在允许范围内"
    if error_type == "json_invalid":
        return "请求体不是有效的 JSON"
    if error_type == "value_error":
        raw_error = context.get("error")
        message = str(raw_error) if raw_error else "参数值不正确"
        return {
            "project_name cannot be null": "项目名称不能为 null",
        }.get(message, message)
    return "参数格式或内容不正确"


def translate_validation_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """只翻译错误描述，type、loc 等协议字段保持稳定英文值。"""
    translated: list[dict[str, Any]] = []
    for error in errors:
        error_type = str(error.get("type", "value_error"))
        context = error.get("ctx") or {}
        location = list(error.get("loc", ()))
        field_name = str(location[-1]) if location else None
        translated.append(
            {
                "type": error_type,
                "loc": location,
                "msg": _translate_message(error_type, context),
                "input": _sanitize_input(
                    error.get("input"),
                    field_name=field_name,
                ),
            }
        )
    return translated

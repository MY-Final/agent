from typing import Any


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
        translated.append(
            {
                "type": error_type,
                "loc": list(error.get("loc", ())),
                "msg": _translate_message(error_type, context),
                "input": error.get("input"),
            }
        )
    return translated

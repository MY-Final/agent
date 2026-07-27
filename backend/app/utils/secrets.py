import re


MASKED_API_KEY_PATTERN = re.compile(r"^(?:\*{8}|.{4}\*{8}.{4})$")


def mask_api_key(api_key: str | None) -> str | None:
    """脱敏 API Key；短密钥完全隐藏，常规密钥仅保留首尾四位。"""

    if not api_key:
        return None
    if len(api_key) <= 8:
        return "********"
    return f"{api_key[:4]}********{api_key[-4:]}"


def looks_like_masked_api_key(api_key: str) -> bool:
    """识别设置页回传的脱敏值，避免其覆盖真实密钥。"""

    return MASKED_API_KEY_PATTERN.fullmatch(api_key) is not None

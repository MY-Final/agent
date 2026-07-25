import re
import uuid
from pathlib import PurePath


_UNSAFE_FILENAME_CHARS = re.compile(r"[^\w.-]+", flags=re.UNICODE)


def sanitize_filename(filename: str) -> str:
    """移除路径信息和危险字符，生成适合对象存储的安全文件名。"""
    basename = PurePath(filename.replace("\\", "/")).name.strip()
    safe_name = _UNSAFE_FILENAME_CHARS.sub("_", basename).strip("._")
    return safe_name[:255] or "未命名文件"


def extract_original_filename(filename: str) -> str:
    basename = PurePath(filename.replace("\\", "/")).name.strip()
    return basename[:512] or "未命名文件"


def build_object_key(task_id: uuid.UUID, original_filename: str) -> str:
    safe_name = sanitize_filename(original_filename)
    return f"tasks/{task_id}/{uuid.uuid4().hex}_{safe_name}"

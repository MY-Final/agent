"""运行时基础设施配置：桌面端系统设置保存，后端下次启动时读取生效。"""

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote



def _runtime_config_dir() -> Path:
    """PyInstaller 打包后 __file__ 指向临时解压目录，配置要放到稳定位置。"""

    if getattr(sys, "frozen", False):
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home())
        return base / "TenderAnalysis"
    return Path(__file__).resolve().parents[2]


RUNTIME_CONFIG_FILE = _runtime_config_dir() / "runtime.env.json"


def load_runtime_config() -> dict[str, Any]:
    """读取运行时配置；文件不存在或损坏时返回空字典。"""

    if not RUNTIME_CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(RUNTIME_CONFIG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_runtime_config(data: dict[str, Any]) -> None:
    RUNTIME_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_CONFIG_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_database_url(postgres: dict[str, Any]) -> str:
    user = str(postgres.get("user") or "")
    password = quote(str(postgres.get("password") or ""), safe="")
    auth = f"{user}:{password}@" if password else f"{user}@"
    return (
        f"postgresql+asyncpg://{auth}"
        f"{postgres['host']}:{postgres['port']}/{postgres['database']}"
    )


def build_redis_url(redis: dict[str, Any]) -> str:
    password = quote(str(redis.get("password") or ""), safe="")
    auth = f":{password}@" if password else ""
    return f"redis://{auth}{redis['host']}:{redis['port']}/{redis.get('db', 0)}"

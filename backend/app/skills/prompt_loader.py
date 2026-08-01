"""提示词模板加载器。

提示词以独立文本文件维护在 app/skills/prompts/ 下，方便直接编辑；
本模块负责加载、占位符校验和渲染。任何模板缺失或占位符不一致都会
在导入阶段直接失败，避免线上运行到一半才发现问题。

部署时可设置环境变量 TENDER_PROMPTS_DIR 指向自定义模板目录，加载
同名模板文件；未设置时，开发环境直接读取仓库内文件，打包环境读取
PyInstaller 内嵌副本。
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

_TOKEN_RE = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")

_BUNDLED_DIR = Path(__file__).resolve().parent / "prompts"

_PROMPT_DIR_ENV = "TENDER_PROMPTS_DIR"

# 模板名 -> (文件名, 期望占位符集合)
_REQUIRED_TEMPLATES: dict[str, tuple[str, set[str]]] = {
    "extract_system": ("extract_system.txt", set()),
    "extract_user": ("extract_user.txt", {"template_description", "tender_text"}),
    "suggest_system": ("suggest_system.txt", set()),
    "suggest_user": ("suggest_user.txt", {"description", "reference_block"}),
}


class PromptTemplate:
    """一个提示词模板，占位符以 {{name}} 形式出现。"""

    __slots__ = ("name", "content", "placeholders")

    def __init__(self, name: str, content: str) -> None:
        self.name = name
        self.content = content
        self.placeholders = frozenset(_TOKEN_RE.findall(content))

    def render(self, **kwargs: Any) -> str:
        """按参数渲染模板，缺少参数时直接报错。"""

        missing = sorted(self.placeholders - kwargs.keys())
        if missing:
            raise ValueError(
                f"提示词模板 {self.name} 缺少渲染参数：{', '.join(missing)}"
            )
        return _TOKEN_RE.sub(
            lambda match: str(kwargs[match.group(1)]),
            self.content,
        )


def prompts_dir() -> Path:
    """返回模板目录：优先外部覆盖目录，其次打包内嵌目录，最后仓库目录。"""

    override = os.environ.get(_PROMPT_DIR_ENV)
    if override:
        path = Path(override).expanduser()
        if not path.is_dir():
            raise RuntimeError(
                f"提示词目录不存在（环境变量 {_PROMPT_DIR_ENV}={override}）"
            )
        return path
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "app" / "skills" / "prompts"
    return _BUNDLED_DIR


def load_prompt_templates(directory: Path | None = None) -> dict[str, PromptTemplate]:
    """加载并校验全部提示词模板，任何异常都立即抛出。"""

    target = directory or prompts_dir()
    templates: dict[str, PromptTemplate] = {}
    for name, (filename, expected) in _REQUIRED_TEMPLATES.items():
        path = target / filename
        if not path.is_file():
            raise RuntimeError(f"缺少提示词模板文件：{path}")
        content = path.read_text(encoding="utf-8").strip()
        template = PromptTemplate(name, content)
        actual = set(template.placeholders)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            detail = (
                f"，缺少：{', '.join(missing)}" if missing else ""
            ) + (f"，多余：{', '.join(extra)}" if extra else "")
            raise RuntimeError(
                f"提示词模板 {filename} 占位符校验失败{detail}"
            )
        templates[name] = template
    return templates


PROMPTS = load_prompt_templates()

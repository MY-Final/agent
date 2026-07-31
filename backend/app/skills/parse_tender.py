import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.schemas.skills.parse import ParseResult, ParseTemplate
from app.skills.llm import TenderLLMClient
from app.skills.parse_template import SEED_PARSE_TEMPLATE
from app.skills.text_extractor import TextExtractor


@dataclass(slots=True, frozen=True)
class TenderDocument:
    filename: str
    object_key: str
    local_path: Path


@dataclass(slots=True, frozen=True)
class ParseOutcome:
    """一次解析的完整产物：结构化结果 + 各文件提取原文（供人工对照）。"""

    result: ParseResult
    source_texts: list[dict[str, Any]]


class ParseTenderSkill:
    """独立标书解析 Skill：文本提取后统一交给 LLM 做结构化抽取。"""

    def __init__(
        self,
        text_extractor: TextExtractor | None = None,
        llm_client: TenderLLMClient | None = None,
    ) -> None:
        self._text_extractor = text_extractor or TextExtractor()
        self._llm_client = llm_client

    async def run(
        self,
        documents: list[TenderDocument],
        template: ParseTemplate = SEED_PARSE_TEMPLATE,
        *,
        task_id: uuid.UUID | None = None,
    ) -> ParseOutcome:
        if not documents:
            raise ValueError("没有可解析的标书文件")

        sections: list[str] = []
        source_texts: list[dict[str, Any]] = []
        for index, document in enumerate(documents, start=1):
            extracted = await self._text_extractor.extract(document.local_path)
            source_texts.append(
                {
                    "filename": document.filename,
                    "extraction_method": extracted.extraction_method,
                    "text": extracted.text,
                }
            )
            sections.append(
                "\n".join(
                    [
                        f"===== 文件 {index}：{document.filename} =====",
                        f"[文本提取方式：{extracted.extraction_method}]",
                        extracted.text,
                    ]
                )
            )

        llm_client = self._llm_client or TenderLLMClient()
        return ParseOutcome(
            result=await llm_client.extract(
                "\n\n".join(sections),
                template,
                task_id=task_id,
            ),
            source_texts=source_texts,
        )

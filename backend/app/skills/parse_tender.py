from dataclasses import dataclass
from pathlib import Path

from app.schemas.skills.parse import ParseResult
from app.skills.llm import TenderLLMClient
from app.skills.text_extractor import TextExtractor


@dataclass(slots=True, frozen=True)
class TenderDocument:
    filename: str
    object_key: str
    local_path: Path


class ParseTenderSkill:
    """独立标书解析 Skill：文本提取后统一交给 LLM 做结构化抽取。"""

    def __init__(
        self,
        text_extractor: TextExtractor | None = None,
        llm_client: TenderLLMClient | None = None,
    ) -> None:
        self._text_extractor = text_extractor or TextExtractor()
        self._llm_client = llm_client

    async def run(self, documents: list[TenderDocument]) -> ParseResult:
        if not documents:
            raise ValueError("没有可解析的标书文件")

        sections: list[str] = []
        for index, document in enumerate(documents, start=1):
            extracted = await self._text_extractor.extract(document.local_path)
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
        return await llm_client.extract("\n\n".join(sections))

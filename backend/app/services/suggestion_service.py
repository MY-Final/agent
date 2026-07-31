from app.schemas.parse_template import TemplateSuggestion
from app.skills.llm import TenderLLMClient


class TemplateSuggestionService:
    """自然语言生成模板建议的编排入口。"""

    @staticmethod
    async def suggest(
        description: str,
        reference_text: str | None = None,
    ) -> TemplateSuggestion:
        return await TenderLLMClient().suggest_template(
            description,
            reference_text,
        )

import logging
import uuid
from decimal import Decimal

from app.core.database import AsyncSessionFactory
from app.models.llm_usage import LLMUsage, LLMUsageStatus


logger = logging.getLogger(__name__)

# 每 100 万 token 的估算单价（USD），用于未接入计价接口的模型成本估算。
_MODEL_PRICES: dict[str, tuple[Decimal, Decimal]] = {
    "gpt-4o": (Decimal("2.50"), Decimal("10.00")),
    "gpt-4o-mini": (Decimal("0.15"), Decimal("0.60")),
    "gpt-4.1": (Decimal("2.00"), Decimal("8.00")),
    "gpt-4.1-mini": (Decimal("0.40"), Decimal("1.60")),
    "gpt-4.1-nano": (Decimal("0.10"), Decimal("0.40")),
    "gpt-4-turbo": (Decimal("10.00"), Decimal("30.00")),
    "gpt-3.5-turbo": (Decimal("0.50"), Decimal("1.50")),
    "deepseek-chat": (Decimal("0.27"), Decimal("1.10")),
    "deepseek-reasoner": (Decimal("0.55"), Decimal("2.19")),
    "qwen-max": (Decimal("2.40"), Decimal("9.60")),
    "qwen-plus": (Decimal("0.80"), Decimal("2.00")),
    "qwen-turbo": (Decimal("0.30"), Decimal("0.60")),
    "glm-4-plus": (Decimal("0.50"), Decimal("2.00")),
    "glm-4-flash": (Decimal("0.10"), Decimal("0.10")),
    "moonshot-v1-8k": (Decimal("1.20"), Decimal("2.40")),
    "moonshot-v1-32k": (Decimal("2.40"), Decimal("4.80")),
    "ernie-4.0-8k": (Decimal("2.00"), Decimal("8.00")),
}
# 未收录模型的兜底单价：按 1 美元 / 3 美元每百万 token 估算。
_DEFAULT_PRICES: tuple[Decimal, Decimal] = (Decimal("1.00"), Decimal("3.00"))


def _estimate_prices(model: str) -> tuple[Decimal, Decimal]:
    return _MODEL_PRICES.get(model, _DEFAULT_PRICES)


class LLMUsageService:
    @staticmethod
    async def record_usage(
        *,
        provider_id: uuid.UUID | None,
        provider_name: str | None,
        model: str,
        purpose: str,
        task_id: uuid.UUID | None,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        latency_ms: int | None,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """记录一次大模型调用；统计失败只写日志，绝不影响主流程。"""

        input_price, output_price = _estimate_prices(model)
        estimated_cost: Decimal | None = None
        if total_tokens:
            estimated_cost = (
                Decimal(prompt_tokens) * input_price
                + Decimal(completion_tokens) * output_price
            ) / Decimal(1_000_000)
        record = LLMUsage(
            provider_id=provider_id,
            provider_name=provider_name,
            model=model,
            purpose=purpose,
            task_id=task_id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            input_price_per_million=input_price,
            output_price_per_million=output_price,
            estimated_cost=estimated_cost,
            latency_ms=latency_ms,
            status=LLMUsageStatus(status),
            error_message=error_message,
        )
        try:
            async with AsyncSessionFactory() as session:
                session.add(record)
                await session.commit()
        except Exception:
            logger.exception("记录 LLM 用量失败，purpose=%s，model=%s", purpose, model)

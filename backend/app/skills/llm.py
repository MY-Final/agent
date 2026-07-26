import json
import logging
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import ValidationError

from app.core.config import settings
from app.core.exceptions import AppException
from app.schemas.skills.parse import ParseResult


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是严谨的中文招标文件结构化抽取器。
只能根据用户提供的原文抽取，禁止补充常识、猜测或编造。
重点识别资格要求、评分办法、废标条款和关键时间节点。
原文没有的信息必须返回 null、空数组或空对象。
qualification.category 使用：资质、业绩、人员、财务、其他。
confidence 为 0 到 1，表示结果受原文清晰度支持的整体置信度。
输出必须严格符合给定 JSON Schema。"""


class TenderLLMClient:
    """OpenAI 兼容结构化输出客户端。"""

    def __init__(self) -> None:
        if settings.llm_api_key is None:
            raise AppException(
                "未配置 LLM_API_KEY，无法执行标书结构化解析",
                code=50301,
                status_code=503,
            )

        options: dict[str, Any] = {
            "api_key": settings.llm_api_key.get_secret_value(),
            "timeout": settings.llm_timeout_seconds,
        }
        if settings.llm_base_url:
            options["base_url"] = settings.llm_base_url
        self._client = AsyncOpenAI(**options)

    async def extract(self, tender_text: str) -> ParseResult:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "请从以下招标文件原文中提取结构化信息：\n\n" + tender_text,
            },
        ]
        schema = ParseResult.model_json_schema()
        try:
            try:
                response = await self._client.chat.completions.create(
                    model=settings.llm_model_name,
                    messages=messages,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "tender_parse_result",
                            # scoring_method、key_dates 是动态字典，因此由 Pydantic
                            # 做最终严格校验，不启用供应商侧 strict 子集限制。
                            "strict": False,
                            "schema": schema,
                        },
                    },
                )
            except BadRequestError as exc:
                # 部分 OpenAI 兼容服务只实现 JSON Mode，仍以 Pydantic 做最终强校验。
                logger.warning(
                    "当前 LLM 不支持 JSON Schema，降级使用 JSON Mode：%s",
                    exc,
                )
                response = await self._client.chat.completions.create(
                    model=settings.llm_model_name,
                    messages=messages,
                    response_format={"type": "json_object"},
                )
        except AuthenticationError as exc:
            raise AppException(
                "大模型鉴权失败，请检查 LLM_API_KEY",
                code=50213,
                status_code=502,
            ) from exc
        except PermissionDeniedError as exc:
            raise AppException(
                "当前密钥无权调用配置的大模型",
                code=50214,
                status_code=502,
            ) from exc
        except RateLimitError as exc:
            raise AppException(
                "大模型服务请求过于频繁或额度不足",
                code=50215,
                status_code=502,
            ) from exc
        except APITimeoutError as exc:
            raise AppException(
                "大模型服务响应超时",
                code=50401,
                status_code=504,
            ) from exc
        except APIConnectionError as exc:
            raise AppException(
                "无法连接大模型服务，请检查 LLM_BASE_URL 和网络",
                code=50216,
                status_code=502,
            ) from exc
        except APIStatusError as exc:
            raise AppException(
                f"大模型服务请求失败，HTTP 状态码：{exc.status_code}",
                code=50217,
                status_code=502,
            ) from exc

        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise AppException(
                "大模型没有返回可用的结构化内容",
                code=50211,
                status_code=502,
            )

        try:
            payload = json.loads(_strip_json_fence(content))
            return ParseResult.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise AppException(
                "大模型返回内容未通过结构化结果校验",
                code=50212,
                status_code=502,
            ) from exc


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return stripped

import json
import logging
from contextlib import suppress
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

from app.core.exceptions import AppException
from app.schemas.parse_template import TemplateSuggestion
from app.schemas.skills.parse import ParseResult, ParseTemplate
from app.services.llm_provider_service import LLMRuntimeConfig, get_current_llm_config
from app.skills.parse_template import (
    SUGGEST_SYSTEM_PROMPT,
    build_extraction_schema,
    build_suggestion_prompt,
    describe_template,
    sanitize_sections,
    with_core_contract,
)


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是严谨的中文招标文件结构化抽取器。
只能根据用户提供的原文抽取，禁止补充常识、猜测或编造。
重点识别资格要求、评分办法、废标条款和关键时间节点。
原文没有的信息必须返回 null、空数组或空对象。
qualification.category 使用：资质、业绩、人员、财务、其他。
confidence 为 0 到 1，表示结果受原文清晰度支持的整体置信度。
输出必须严格符合给定 JSON Schema，data 中不得新增模板之外的键。"""


class TenderLLMClient:
    """OpenAI 兼容结构化输出客户端。"""

    async def _make_client(
        self,
    ) -> tuple[LLMRuntimeConfig, AsyncOpenAI]:
        config = await get_current_llm_config()
        if not config.api_key:
            raise AppException(
                "未配置可用的大模型 API Key，请新增默认提供商或配置 LLM_API_KEY",
                code=50301,
                status_code=503,
            )

        options: dict[str, Any] = {
            "api_key": config.api_key,
            "timeout": config.timeout_seconds,
        }
        if config.base_url:
            options["base_url"] = config.base_url
        client = AsyncOpenAI(**options)
        return config, client

    async def _request_content(
        self,
        config: LLMRuntimeConfig,
        client: AsyncOpenAI,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any],
    ) -> str:
        """发起结构化输出请求并统一映射上游错误，返回原始内容文本。"""

        completion_options = _completion_options(config)
        try:
            try:
                response = await client.chat.completions.create(
                    model=config.default_model,
                    messages=messages,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema_name,
                            # 动态部分由 Pydantic 做最终严格校验，
                            # 不启用供应商侧 strict 子集限制。
                            "strict": False,
                            "schema": schema,
                        },
                    },
                    **completion_options,
                )
            except BadRequestError as exc:
                # 部分 OpenAI 兼容服务只实现 JSON Mode，仍以 Pydantic 做最终强校验。
                logger.warning(
                    "当前 LLM 不支持 JSON Schema，降级使用 JSON Mode：%s",
                    exc,
                )
                response = await client.chat.completions.create(
                    model=config.default_model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    **completion_options,
                )
        except AuthenticationError as exc:
            raise AppException(
                "大模型鉴权失败，请检查当前提供商的 API Key",
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
                "无法连接大模型服务，请检查当前提供商地址和网络",
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
        return content

    async def extract(
        self,
        tender_text: str,
        template: ParseTemplate,
    ) -> ParseResult:
        config, client = await self._make_client()
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "请从以下招标文件原文中提取结构化信息，严格按模板填写 data：\n\n"
                    f"{describe_template(template)}\n\n"
                    "原文：\n"
                    + tender_text
                ),
            },
        ]
        schema = build_extraction_schema(template)
        try:
            content = await self._request_content(
                config,
                client,
                messages,
                "tender_parse_result",
                schema,
            )
        finally:
            with suppress(Exception):
                await client.close()

        try:
            payload = json.loads(_strip_json_fence(content))
            return ParseResult(
                template=template,
                data=payload.get("data") or {},
                raw_summary=payload.get("raw_summary"),
                confidence=payload.get("confidence"),
            )
        except (json.JSONDecodeError, ValidationError) as exc:
            raise AppException(
                "大模型返回内容未通过结构化结果校验",
                code=50212,
                status_code=502,
            ) from exc

    async def suggest_template(
        self,
        description: str,
        reference_text: str | None = None,
    ) -> TemplateSuggestion:
        """根据自然语言需求生成模板建议，人工确认后再落库。"""

        config, client = await self._make_client()
        messages = [
            {"role": "system", "content": SUGGEST_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": build_suggestion_prompt(description, reference_text),
            },
        ]
        schema = TemplateSuggestion.model_json_schema()
        try:
            content = await self._request_content(
                config,
                client,
                messages,
                "tender_template_suggestion",
                schema,
            )
        finally:
            with suppress(Exception):
                await client.close()

        try:
            payload = json.loads(_strip_json_fence(content))
            suggestion = TemplateSuggestion.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise AppException(
                "大模型返回的模板建议未通过校验",
                code=50222,
                status_code=502,
            ) from exc
        return suggestion.model_copy(
            update={
                "sections": with_core_contract(
                    sanitize_sections(suggestion.sections)
                )
            }
        )


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _completion_options(config: LLMRuntimeConfig) -> dict[str, Any]:
    """只向 OpenAI SDK 传递明确允许的扩展参数。"""

    allowed_keys = {
        "temperature",
        "top_p",
        "max_tokens",
        "frequency_penalty",
        "presence_penalty",
        "seed",
    }
    return {
        key: value
        for key, value in config.extra_config.items()
        if key in allowed_keys and value is not None
    }

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from openai import (
    APIError,
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
from app.core.llm_stream import LLM_DELTA_CALLBACK
from app.schemas.parse_template import TemplateSuggestion
from app.schemas.skills.parse import ParseResult, ParseTemplate, SectionKind
from app.services.llm_provider_service import LLMRuntimeConfig, get_current_llm_config
from app.services.llm_usage_service import LLMUsageService
from app.skills.prompt_loader import PROMPTS
from app.skills.parse_template import (
    build_extraction_schema,
    build_suggestion_prompt,
    describe_template,
    sanitize_sections,
    with_core_contract,
)


logger = logging.getLogger(__name__)

# 瞬时性故障（限流 / 5xx / 上游暂不可用）允许自动重试。
_RETRYABLE_ERROR_CODES = {50215, 50217, 50218}
_MAX_RETRIES = 2


@dataclass(slots=True)
class LLMCallTrace:
    """一次大模型调用的完整痕迹：发送的消息、响应 Schema 与原始返回。"""

    messages: list[dict[str, str]] = field(default_factory=list)
    schema: dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""


class TenderLLMClient:
    """OpenAI 兼容结构化输出客户端。"""

    def __init__(self) -> None:
        self.last_trace: LLMCallTrace | None = None

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
        schema: dict[str, Any] | None,
        *,
        purpose: str,
        task_id: uuid.UUID | None = None,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
        on_thinking: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """发起请求：有流式回调时走流式，否则走一次性请求。

        瞬时性故障（限流、5xx、上游暂不可用）自动重试；
        流式场景下若已向客户端输出过增量，则不再重试，避免内容重复。
        """

        delta_callback = on_delta or LLM_DELTA_CALLBACK.get()
        delivered = False

        async def tracked_delta(piece: str) -> None:
            nonlocal delivered
            delivered = True
            await delta_callback(piece)

        async def tracked_thinking(piece: str) -> None:
            nonlocal delivered
            # 思考过程也属于已输出的内容：已展示后不再整轮重试，避免重复。
            delivered = True
            if on_thinking is not None:
                await on_thinking(piece)

        for attempt in range(_MAX_RETRIES + 1):
            delivered = False
            try:
                if delta_callback is not None:
                    return await self._stream_content(
                        config,
                        client,
                        messages,
                        schema_name,
                        schema,
                        purpose=purpose,
                        task_id=task_id,
                        on_delta=tracked_delta,
                        on_thinking=(
                            tracked_thinking if on_thinking is not None else None
                        ),
                    )
                return await self._request_content_once(
                    config,
                    client,
                    messages,
                    schema_name,
                    schema,
                    purpose=purpose,
                    task_id=task_id,
                )
            except AppException as exc:
                if (
                    exc.code not in _RETRYABLE_ERROR_CODES
                    or attempt >= _MAX_RETRIES
                    or delivered
                ):
                    raise
                logger.warning(
                    "大模型调用遇到瞬时故障，第 %s/%s 次重试：%s",
                    attempt + 1,
                    _MAX_RETRIES,
                    exc.message,
                )
                await asyncio.sleep(1.0 * (attempt + 1))
        raise RuntimeError("大模型调用重试循环异常退出")  # pragma: no cover

    async def _request_content_once(
        self,
        config: LLMRuntimeConfig,
        client: AsyncOpenAI,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any] | None,
        *,
        purpose: str,
        task_id: uuid.UUID | None = None,
    ) -> str:
        """一次性（非流式）结构化输出请求，统一映射上游错误并记录用量。"""

        started = time.perf_counter()
        error_message: str | None = None
        completion_options = _completion_options(config)
        response_format: dict[str, Any] | None = None
        if schema is not None:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    # 动态部分由 Pydantic 做最终严格校验，
                    # 不启用供应商侧 strict 子集限制。
                    "strict": False,
                    "schema": schema,
                },
            }
        try:
            try:
                request_options: dict[str, Any] = {
                    "model": config.default_model,
                    "messages": messages,
                    **completion_options,
                }
                if response_format is not None:
                    request_options["response_format"] = response_format
                response = await client.chat.completions.create(**request_options)
            except BadRequestError as exc:
                if schema is None:
                    raise
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
            error_message = "大模型鉴权失败，请检查当前提供商的 API Key"
            raise AppException(error_message, code=50213, status_code=502) from exc
        except PermissionDeniedError as exc:
            error_message = "当前密钥无权调用配置的大模型"
            raise AppException(error_message, code=50214, status_code=502) from exc
        except RateLimitError as exc:
            error_message = "大模型服务请求过于频繁或额度不足"
            raise AppException(error_message, code=50215, status_code=502) from exc
        except APITimeoutError as exc:
            error_message = "大模型服务响应超时"
            raise AppException(error_message, code=50401, status_code=504) from exc
        except APIConnectionError as exc:
            error_message = "无法连接大模型服务，请检查当前提供商地址和网络"
            raise AppException(error_message, code=50216, status_code=502) from exc
        except APIStatusError as exc:
            error_message = f"大模型服务请求失败，HTTP 状态码：{exc.status_code}"
            raise AppException(error_message, code=50217, status_code=502) from exc
        except APIError as exc:
            # 上游返回无法解析的错误（如 502/503 网关错误体），属于瞬时故障。
            error_message = "大模型服务暂时不可用，请稍后重试"
            raise AppException(error_message, code=50218, status_code=502) from exc
        finally:
            if error_message is not None:
                await self._record_usage(
                    config,
                    purpose,
                    task_id,
                    status="failed",
                    error_message=error_message,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )

        latency_ms = int((time.perf_counter() - started) * 1000)
        content = response.choices[0].message.content if response.choices else None
        if not content:
            await self._record_usage(
                config,
                purpose,
                task_id,
                status="failed",
                error_message="大模型没有返回可用的结构化内容",
                latency_ms=latency_ms,
            )
            raise AppException(
                "大模型没有返回可用的结构化内容",
                code=50211,
                status_code=502,
            )
        usage = response.usage
        await self._record_usage(
            config,
            purpose,
            task_id,
            status="success",
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
            latency_ms=latency_ms,
        )
        return content

    async def _stream_content(
        self,
        config: LLMRuntimeConfig,
        client: AsyncOpenAI,
        messages: list[dict[str, str]],
        schema_name: str,
        schema: dict[str, Any] | None,
        *,
        purpose: str,
        task_id: uuid.UUID | None,
        on_delta: Callable[[str], Awaitable[None]],
        on_thinking: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """流式请求：逐段回调增量内容，返回完整内容。

        结构化请求（schema 非空）按「带 usage → 不带 usage → JSON Mode 流式
        → 非流式」逐级降级；纯文本请求直接流式。非流式降级时把完整内容
        作为一次 delta 回调，调用方无需感知差异。
        """

        started = time.perf_counter()
        error_message: str | None = None
        completion_options = _completion_options(config)
        response_format: dict[str, Any] | None = None
        if schema is not None:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    # 与 _request_content 保持一致：动态部分由 Pydantic 做最终校验。
                    "strict": False,
                    "schema": schema,
                },
            }
        delivered = False

        async def tracked_on_delta(piece: str) -> None:
            nonlocal delivered
            delivered = True
            await on_delta(piece)

        try:
            try:
                request_options: dict[str, Any] = {
                    "model": config.default_model,
                    "messages": messages,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                    **completion_options,
                }
                if response_format is not None:
                    request_options["response_format"] = response_format
                stream = await client.chat.completions.create(**request_options)
            except BadRequestError as exc:
                logger.warning(
                    "当前 LLM 不支持 include_usage 流式参数，降级重试：%s",
                    exc,
                )
                retry_options: dict[str, Any] = {
                    "model": config.default_model,
                    "messages": messages,
                    "stream": True,
                    **completion_options,
                }
                if response_format is not None:
                    retry_options["response_format"] = response_format
                stream = await client.chat.completions.create(**retry_options)
            content_parts, usage = await self._consume_stream(
                stream,
                tracked_on_delta,
                on_thinking,
            )
        except BadRequestError as exc:
            if schema is None:
                # 纯文本流式仍失败：退回一次性请求，整段作为一次 delta。
                logger.warning(
                    "当前 LLM 不支持流式输出，降级为非流式：%s",
                    exc,
                )
                content = await self._request_content_once(
                    config,
                    client,
                    messages,
                    schema_name,
                    schema,
                    purpose=purpose,
                    task_id=task_id,
                )
                await on_delta(content)
                return content
            # json_schema 流式不可用：部分兼容服务只支持 JSON Mode，再试一次。
            logger.warning(
                "当前 LLM 不支持流式 JSON Schema，降级 JSON Mode 流式：%s",
                exc,
            )
            try:
                stream = await client.chat.completions.create(
                    model=config.default_model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    stream=True,
                    **completion_options,
                )
                content_parts, usage = await self._consume_stream(
                    stream,
                    tracked_on_delta,
                    on_thinking,
                )
            except BadRequestError as exc2:
                # 流式整体不可用：退回一次性请求（该路径不会再进入流式），
                # 整段内容作为一次 delta，前端仍能收到完整输出。
                logger.warning(
                    "当前 LLM 不支持流式输出，降级为非流式：%s",
                    exc2,
                )
                content = await self._request_content_once(
                    config,
                    client,
                    messages,
                    schema_name,
                    schema,
                    purpose=purpose,
                    task_id=task_id,
                )
                await on_delta(content)
                return content
        except AuthenticationError as exc:
            error_message = "大模型鉴权失败，请检查当前提供商的 API Key"
            raise AppException(error_message, code=50213, status_code=502) from exc
        except PermissionDeniedError as exc:
            error_message = "当前密钥无权调用配置的大模型"
            raise AppException(error_message, code=50214, status_code=502) from exc
        except RateLimitError as exc:
            error_message = "大模型服务请求过于频繁或额度不足"
            raise AppException(error_message, code=50215, status_code=502) from exc
        except APITimeoutError as exc:
            error_message = "大模型服务响应超时"
            raise AppException(error_message, code=50401, status_code=504) from exc
        except APIConnectionError as exc:
            error_message = "无法连接大模型服务，请检查当前提供商地址和网络"
            raise AppException(error_message, code=50216, status_code=502) from exc
        except APIStatusError as exc:
            error_message = f"大模型服务请求失败，HTTP 状态码：{exc.status_code}"
            raise AppException(error_message, code=50217, status_code=502) from exc
        except APIError as exc:
            if not delivered:
                # 流式通道不可用（如网关 200 后返回错误事件）且尚未输出任何内容：
                # 直接降级为非流式请求，整段内容作为一次 delta。
                logger.warning(
                    "流式响应中断且尚未输出内容，降级为非流式：%s",
                    exc,
                )
                content = await self._request_content_once(
                    config,
                    client,
                    messages,
                    schema_name,
                    schema,
                    purpose=purpose,
                    task_id=task_id,
                )
                await on_delta(content)
                return content
            # 上游返回无法解析的错误（如网关 502/503），属于瞬时故障。
            error_message = "大模型服务暂时不可用，请稍后重试"
            raise AppException(error_message, code=50218, status_code=502) from exc
        finally:
            if error_message is not None:
                await self._record_usage(
                    config,
                    purpose,
                    task_id,
                    status="failed",
                    error_message=error_message,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )

        content = "".join(content_parts)
        if not content.strip():
            await self._record_usage(
                config,
                purpose,
                task_id,
                status="failed",
                error_message="大模型没有返回可用的结构化内容",
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            raise AppException(
                "大模型没有返回可用的结构化内容",
                code=50211,
                status_code=502,
            )
        await self._record_usage(
            config,
            purpose,
            task_id,
            status="success",
            prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return content

    async def _consume_stream(
        self,
        stream: Any,
        on_delta: Callable[[str], Awaitable[None]],
        on_thinking: Callable[[str], Awaitable[None]] | None = None,
    ) -> tuple[list[str], Any]:
        """消费流式响应：累计内容并逐段回调，返回（内容片段列表, usage）。"""

        content_parts: list[str] = []
        usage: Any = None
        async for chunk in stream:
            usage = getattr(chunk, "usage", None) or usage
            if not chunk.choices:
                continue
            piece = getattr(chunk.choices[0].delta, "content", None)
            if piece:
                content_parts.append(piece)
                await on_delta(piece)
            if on_thinking is not None:
                delta = chunk.choices[0].delta
                thinking_piece = getattr(delta, "reasoning_content", None) or getattr(
                    delta,
                    "thinking_content",
                    None,
                )
                if thinking_piece:
                    await on_thinking(thinking_piece)
        return content_parts, usage

    @staticmethod
    async def _record_usage(
        config: LLMRuntimeConfig,
        purpose: str,
        task_id: uuid.UUID | None,
        *,
        status: str,
        error_message: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        latency_ms: int | None = None,
    ) -> None:
        """用量记录失败只写日志，绝不影响解析/建议主流程。"""

        with suppress(Exception):
            await LLMUsageService.record_usage(
                provider_id=config.provider_id,
                provider_name=config.provider_name,
                model=config.default_model,
                purpose=purpose,
                task_id=task_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                status=status,
                error_message=error_message,
            )

    async def extract(
        self,
        tender_text: str,
        template: ParseTemplate,
        *,
        task_id: uuid.UUID | None = None,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> ParseResult:
        config, client = await self._make_client()
        messages = [
            {"role": "system", "content": PROMPTS["extract_system"].content},
            {
                "role": "user",
                "content": PROMPTS["extract_user"].render(
                    template_description=describe_template(template),
                    tender_text=tender_text,
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
                purpose="parse",
                task_id=task_id,
                on_delta=on_delta,
            )
        finally:
            with suppress(Exception):
                await client.close()

        self.last_trace = LLMCallTrace(
            messages=messages,
            schema=schema,
            raw_response=content,
        )
        try:
            payload = json.loads(_strip_json_fence(content))
            data = _fill_missing_template_data(template, payload.get("data") or {})
            return ParseResult(
                template=template,
                data=data,
                raw_summary=payload.get("raw_summary"),
                confidence=payload.get("confidence"),
            )
        except json.JSONDecodeError as exc:
            logger.warning(
                "大模型返回内容不是有效 JSON：%s",
                content,
            )
            raise AppException(
                "大模型返回内容不是有效 JSON，未通过结构化结果校验。"
                "\n\n大模型原始返回：\n"
                + _format_raw_llm_content(content),
                code=50212,
                status_code=502,
            ) from exc
        except ValidationError as exc:
            reason = _first_validation_error(exc)
            logger.warning(
                "大模型结构化结果校验失败：%s | 原始内容：%s",
                reason,
                content,
            )
            raise AppException(
                f"大模型返回内容未通过结构化结果校验：{reason}"
                "\n\n大模型原始返回：\n"
                + _format_raw_llm_content(content),
                code=50212,
                status_code=502,
            ) from exc

    async def suggest_template(
        self,
        description: str,
        reference_text: str | None = None,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> TemplateSuggestion:
        """根据自然语言需求生成模板建议，人工确认后再落库。"""

        config, client = await self._make_client()
        messages = [
            {"role": "system", "content": PROMPTS["suggest_system"].content},
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
                purpose="template_suggest",
                on_delta=on_delta,
            )
        finally:
            with suppress(Exception):
                await client.close()

        self.last_trace = LLMCallTrace(
            messages=messages,
            schema=schema,
            raw_response=content,
        )
        try:
            payload = json.loads(_strip_json_fence(content))
            suggestion = TemplateSuggestion.model_validate(payload)
        except json.JSONDecodeError as exc:
            logger.warning("大模型返回的模板建议不是有效 JSON：%s", content)
            raise AppException(
                "大模型返回的模板建议不是有效 JSON。"
                "\n\n大模型原始返回：\n"
                + _format_raw_llm_content(content),
                code=50222,
                status_code=502,
            ) from exc
        except ValidationError as exc:
            reason = _first_validation_error(exc)
            logger.warning("大模型模板建议校验失败：%s | 原始内容：%s", reason, content)
            raise AppException(
                f"大模型返回的模板建议未通过校验：{reason}"
                "\n\n大模型原始返回：\n"
                + _format_raw_llm_content(content),
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

    async def chat(
        self,
        *,
        system_prompt: str,
        history: list[dict[str, str]],
        context: str,
        question: str,
        task_id: uuid.UUID | None = None,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
        on_thinking: Callable[[str], Awaitable[None]] | None = None,
    ) -> str:
        """基于给定背景信息流式回答用户问题（纯文本，无 JSON Schema）。"""

        config, client = await self._make_client()
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append(
            {
                "role": "user",
                "content": PROMPTS["chat_user"].render(
                    context=context,
                    question=question,
                ),
            }
        )
        try:
            content = await self._request_content(
                config,
                client,
                messages,
                "",
                None,
                purpose="chat",
                task_id=task_id,
                on_delta=on_delta,
                on_thinking=on_thinking,
            )
        finally:
            with suppress(Exception):
                await client.close()
        return content


def _strip_json_fence(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        return "\n".join(lines[1:-1]).strip()
    return stripped


def _format_raw_llm_content(content: str, limit: int = 3000) -> str:
    """把大模型原始返回整理成可读文本；有效 JSON 会格式化，超长则截断。"""

    text = (content or "").strip()
    if not text:
        return "<空响应>"
    try:
        text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        pass
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...(已截断，完整内容见服务端日志)"


def _first_validation_error(exc: ValidationError) -> str:
    first = exc.errors()[0]
    location = ".".join(str(part) for part in first.get("loc", ()))
    message = first.get("msg", str(exc))
    return f"{location} {message}".strip() or str(exc)


def _fill_missing_template_data(
    template: ParseTemplate,
    data: dict[str, Any],
) -> dict[str, Any]:
    """把 LLM 漏掉的区块/字段补成默认空值，避免整份结果被误判失败。"""

    filled: dict[str, Any] = dict(data or {})
    for section in template.sections:
        value = filled.get(section.id)
        if value is None:
            if section.kind == SectionKind.GRID:
                # grid 缺失时也要补全字段默认值，避免校验误报"缺少字段"。
                filled[section.id] = {
                    field.key: None for field in section.fields
                }
            elif section.kind == SectionKind.KEY_VALUE:
                filled[section.id] = {}
            else:
                filled[section.id] = []
            continue
        if section.kind == SectionKind.GRID and isinstance(value, dict):
            grid = dict(value)
            for field in section.fields:
                grid.setdefault(field.key, None)
            filled[section.id] = grid
    return filled


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

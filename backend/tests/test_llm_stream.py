import asyncio
import json
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock

from openai import APIError, BadRequestError

from app.core.exceptions import AppException
from app.core.llm_stream import reset_llm_stream_handlers, set_llm_stream_handlers
from app.core.sse import EventBridge, sse_event
from app.schemas.parse_template import TemplateSuggestion
from app.services.llm_provider_service import LLMRuntimeConfig
from app.skills.llm import TenderLLMClient
from app.skills.parse_template import SEED_PARSE_TEMPLATE


def _runtime_config() -> LLMRuntimeConfig:
    return LLMRuntimeConfig(
        source="database",
        provider_id=uuid.uuid4(),
        provider_name="测试提供商",
        provider_type="openai_compatible",
        base_url="https://example.com/v1",
        api_key="sk-test-secret",
        default_model="test-model",
        timeout_seconds=120,
        extra_config={},
    )


def _chunk(piece: str | None = None, usage: SimpleNamespace | None = None) -> SimpleNamespace:
    delta = SimpleNamespace(content=piece) if piece is not None else None
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=usage)


def _reasoning_chunk(reasoning: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=None, reasoning_content=reasoning)
            )
        ],
        usage=None,
    )


class StreamContentTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_captures_reasoning_content(self) -> None:
        collected: list[str] = []
        thinking: list[str] = []

        async def collect(piece: str) -> None:
            collected.append(piece)

        async def think(piece: str) -> None:
            thinking.append(piece)

        async def create_stream(*_args: object, **_kwargs: object) -> object:
            return _async_chunks(
                _reasoning_chunk("先检查资格要求部分"),
                _chunk("答案"),
            )

        config = _runtime_config()
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_stream)),
            close=mock.AsyncMock(),
        )
        with mock.patch(
            "app.skills.llm.LLMUsageService.record_usage",
            new=mock.AsyncMock(),
        ):
            content = await TenderLLMClient()._stream_content(
                config,
                client,
                [{"role": "user", "content": "hi"}],
                "",
                None,
                purpose="chat",
                task_id=None,
                on_delta=collect,
                on_thinking=think,
            )

        self.assertEqual(content, "答案")
        self.assertEqual(collected, ["答案"])
        self.assertEqual(thinking, ["先检查资格要求部分"])

    async def test_chat_plain_stream_omits_response_format(self) -> None:
        collected: list[str] = []

        async def collect(piece: str) -> None:
            collected.append(piece)

        captured: dict[str, object] = {}

        async def create(*_args: object, **_kwargs: object) -> object:
            captured["kwargs"] = _kwargs
            return _async_chunks(_chunk("你"), _chunk("好"))

        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
            close=mock.AsyncMock(),
        )
        with (
            mock.patch("app.skills.llm.AsyncOpenAI", return_value=client),
            mock.patch(
                "app.skills.llm.get_current_llm_config",
                new=mock.AsyncMock(return_value=_runtime_config()),
            ),
            mock.patch(
                "app.skills.llm.LLMUsageService.record_usage",
                new=mock.AsyncMock(),
            ),
        ):
            content = await TenderLLMClient().chat(
                system_prompt="系统提示",
                history=[
                    {"role": "user", "content": "之前的问题"},
                    {"role": "assistant", "content": "之前的回答"},
                ],
                context="结构化解析结果",
                question="项目工期是多久？",
                on_delta=collect,
            )

        self.assertEqual(content, "你好")
        self.assertEqual(collected, ["你", "好"])
        kwargs = captured["kwargs"]
        assert isinstance(kwargs, dict)
        self.assertNotIn("response_format", kwargs)
        self.assertIs(kwargs["stream"], True)
        messages = kwargs["messages"]
        assert isinstance(messages, list)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("项目工期是多久？", messages[-1]["content"])

    async def test_stream_api_error_maps_to_friendly_message(self) -> None:
        collected: list[str] = []

        async def collect(piece: str) -> None:
            collected.append(piece)

        async def failing_stream() -> object:
            yield _chunk("部分内容")
            raise APIError(
                "Upstream service temporarily unavailable",
                mock.Mock(),
                body=None,
            )

        async def create(*_args: object, **_kwargs: object) -> object:
            return failing_stream()

        config = _runtime_config()
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
            close=mock.AsyncMock(),
        )
        with mock.patch(
            "app.skills.llm.LLMUsageService.record_usage",
            new=mock.AsyncMock(),
        ):
            with self.assertRaises(AppException) as ctx:
                await TenderLLMClient()._stream_content(
                    config,
                    client,
                    [{"role": "user", "content": "hi"}],
                    "tender_parse_result",
                    {},
                    purpose="parse",
                    task_id=None,
                    on_delta=collect,
                )

        self.assertEqual(ctx.exception.code, 50218)
        self.assertIn("暂时不可用", ctx.exception.message)
        # 已经输出过增量，不触发重试。
        self.assertEqual(collected, ["部分内容"])

    async def test_stream_api_error_before_content_falls_back_to_non_streaming(self) -> None:
        collected: list[str] = []

        async def collect(piece: str) -> None:
            collected.append(piece)

        async def failing_stream() -> object:
            if False:
                yield None
            raise APIError(
                "Upstream service temporarily unavailable",
                mock.Mock(),
                body=None,
            )

        full_response = SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content="完整结果"))
            ],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        )
        remaining = [failing_stream, full_response]

        async def create(*_args: object, **_kwargs: object) -> object:
            step = remaining.pop(0)
            if callable(step):
                return step()
            return step

        config = _runtime_config()
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
            close=mock.AsyncMock(),
        )
        with mock.patch(
            "app.skills.llm.LLMUsageService.record_usage",
            new=mock.AsyncMock(),
        ):
            content = await TenderLLMClient()._stream_content(
                config,
                client,
                [{"role": "user", "content": "hi"}],
                "tender_parse_result",
                {},
                purpose="parse",
                task_id=None,
                on_delta=collect,
            )

        self.assertEqual(content, "完整结果")
        self.assertEqual(collected, ["完整结果"])
        self.assertEqual(len(remaining), 0)

    async def test_retries_transient_failures(self) -> None:
        payload = json.dumps(
            {
                "data": {
                    "overview": {"project_name": "测试项目"},
                    "qualifications": [],
                    "scoring_method": {},
                    "key_dates": {},
                    "disqualification_items": [],
                    "other_key_points": [],
                },
                "raw_summary": None,
                "confidence": 0.9,
            },
            ensure_ascii=False,
        )
        full_response = SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=payload))
            ],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        )
        remaining = [
            APIError(
                "Upstream service temporarily unavailable",
                mock.Mock(),
                body=None,
            ),
            APIError(
                "Upstream service temporarily unavailable",
                mock.Mock(),
                body=None,
            ),
            full_response,
        ]

        async def create(*_args: object, **_kwargs: object) -> object:
            step = remaining.pop(0)
            if isinstance(step, Exception):
                raise step
            return step

        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
            close=mock.AsyncMock(),
        )
        with (
            mock.patch("app.skills.llm.AsyncOpenAI", return_value=client),
            mock.patch(
                "app.skills.llm.get_current_llm_config",
                new=mock.AsyncMock(return_value=_runtime_config()),
            ),
            mock.patch(
                "app.skills.llm.LLMUsageService.record_usage",
                new=mock.AsyncMock(),
            ),
        ):
            result = await TenderLLMClient().extract("测试标书原文", SEED_PARSE_TEMPLATE)

        self.assertEqual(result.project_name, "测试项目")
        self.assertEqual(len(remaining), 0)

    async def test_extract_with_context_callback_does_not_recursively_stream(self) -> None:
        """回归：上下文钩子已设置且提供商拒绝全部流式格式时，降级非流式一次完成。"""

        payload = json.dumps(
            {
                "data": {
                    "overview": {"project_name": "测试项目"},
                    "qualifications": [],
                    "scoring_method": {},
                    "key_dates": {},
                    "disqualification_items": [],
                    "other_key_points": [],
                },
                "raw_summary": None,
                "confidence": 0.9,
            },
            ensure_ascii=False,
        )
        full_response = SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=payload))
            ],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        )
        remaining = [_bad_request(), _bad_request(), _bad_request(), full_response]

        async def create(*_args: object, **_kwargs: object) -> object:
            step = remaining.pop(0)
            if isinstance(step, Exception):
                raise step
            return step

        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
            close=mock.AsyncMock(),
        )
        collected: list[str] = []

        async def collect(piece: str) -> None:
            collected.append(piece)

        llm_client = TenderLLMClient()
        tokens = set_llm_stream_handlers(collect, None)
        try:
            with (
                mock.patch("app.skills.llm.AsyncOpenAI", return_value=client),
                mock.patch(
                    "app.skills.llm.get_current_llm_config",
                    new=mock.AsyncMock(return_value=_runtime_config()),
                ),
                mock.patch(
                    "app.skills.llm.LLMUsageService.record_usage",
                    new=mock.AsyncMock(),
                ),
            ):
                result = await llm_client.extract("测试标书原文", SEED_PARSE_TEMPLATE)
        finally:
            reset_llm_stream_handlers(tokens)

        self.assertEqual(result.project_name, "测试项目")
        self.assertEqual(collected, [payload])
        self.assertEqual(len(remaining), 0)

    async def test_extract_records_call_trace(self) -> None:
        payload = json.dumps(
            {
                "data": {
                    "overview": {"project_name": "测试项目"},
                    "qualifications": [],
                    "scoring_method": {},
                    "key_dates": {},
                    "disqualification_items": [],
                    "other_key_points": [],
                },
                "raw_summary": None,
                "confidence": 0.9,
            },
            ensure_ascii=False,
        )
        full_response = SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=payload))
            ],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=9, total_tokens=14),
        )

        async def create(*_args: object, **_kwargs: object) -> object:
            return full_response

        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
            close=mock.AsyncMock(),
        )
        llm_client = TenderLLMClient()
        with (
            mock.patch("app.skills.llm.AsyncOpenAI", return_value=client),
            mock.patch(
                "app.skills.llm.get_current_llm_config",
                new=mock.AsyncMock(return_value=_runtime_config()),
            ),
            mock.patch(
                "app.skills.llm.LLMUsageService.record_usage",
                new=mock.AsyncMock(),
            ),
        ):
            result = await llm_client.extract("测试标书原文", SEED_PARSE_TEMPLATE)

        self.assertEqual(result.project_name, "测试项目")
        trace = llm_client.last_trace
        self.assertIsNotNone(trace)
        assert trace is not None
        self.assertEqual(trace.messages[0]["role"], "system")
        self.assertEqual(trace.messages[1]["role"], "user")
        self.assertIn("测试标书原文", trace.messages[1]["content"])
        self.assertIn("data", trace.schema["properties"])
        self.assertEqual(json.loads(trace.raw_response)["data"]["overview"]["project_name"], "测试项目")

    async def test_stream_delivers_deltas_and_returns_full_content(self) -> None:
        collected: list[str] = []
        config = _runtime_config()

        async def collect(piece: str) -> None:
            collected.append(piece)

        async def create_stream(*_args: object, **_kwargs: object) -> object:
            return _async_chunks(_chunk("你"), _chunk("好"))

        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_stream)),
            close=mock.AsyncMock(),
        )

        with mock.patch(
            "app.skills.llm.LLMUsageService.record_usage",
            new=mock.AsyncMock(),
        ):
            content = await TenderLLMClient()._stream_content(
                config,
                client,
                [{"role": "user", "content": "hi"}],
                "tender_parse_result",
                {},
                purpose="parse",
                task_id=None,
                on_delta=collect,
            )

        self.assertEqual(content, "你好")
        self.assertEqual(collected, ["你", "好"])

    async def test_stream_falls_back_to_non_streaming(self) -> None:
        collected: list[str] = []
        async def collect(piece: str) -> None:
            collected.append(piece)

        full_response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="一次性返回内容")
                )
            ],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        )
        remaining = [
            _bad_request(),
            _bad_request(),
            _bad_request(),
            full_response,
        ]

        async def create(*_args: object, **_kwargs: object) -> object:
            step = remaining.pop(0)
            if isinstance(step, Exception):
                raise step
            return step

        config = _runtime_config()
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
            close=mock.AsyncMock(),
        )

        with mock.patch(
            "app.skills.llm.LLMUsageService.record_usage",
            new=mock.AsyncMock(),
        ):
            content = await TenderLLMClient()._stream_content(
                config,
                client,
                [{"role": "user", "content": "hi"}],
                "tender_parse_result",
                {},
                purpose="parse",
                task_id=None,
                on_delta=collect,
            )

        self.assertEqual(content, "一次性返回内容")
        self.assertEqual(collected, ["一次性返回内容"])
        self.assertEqual(len(remaining), 0)

    async def test_stream_falls_back_to_json_mode_streaming(self) -> None:
        collected: list[str] = []

        async def collect(piece: str) -> None:
            collected.append(piece)

        remaining = [
            _bad_request(),
            _bad_request(),
        ]

        async def create(*_args: object, **_kwargs: object) -> object:
            step = remaining.pop(0) if remaining else None
            if step is not None:
                raise step
            return _async_chunks(_chunk("{"), _chunk("}"))

        config = _runtime_config()
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
            close=mock.AsyncMock(),
        )

        with mock.patch(
            "app.skills.llm.LLMUsageService.record_usage",
            new=mock.AsyncMock(),
        ):
            content = await TenderLLMClient()._stream_content(
                config,
                client,
                [{"role": "user", "content": "hi"}],
                "tender_parse_result",
                {},
                purpose="parse",
                task_id=None,
                on_delta=collect,
            )

        self.assertEqual(content, "{}")
        self.assertEqual(collected, ["{", "}"])

    async def test_extract_streams_to_callback(self) -> None:
        payload = json.dumps(
            {
                "data": {
                    "overview": {"project_name": "测试项目"},
                    "qualifications": [],
                    "scoring_method": {},
                    "key_dates": {},
                    "disqualification_items": [],
                    "other_key_points": [],
                },
                "raw_summary": None,
                "confidence": 0.9,
            },
            ensure_ascii=False,
        )
        # 把完整 JSON 拆成多个增量片段模拟真实流式返回。
        pieces = [payload[:10], payload[10:30], payload[30:]]
        chunks = [_chunk(piece) for piece in pieces]
        chunks.append(_chunk(usage=SimpleNamespace(prompt_tokens=5, completion_tokens=9, total_tokens=14)))

        collected: list[str] = []

        async def collect(piece: str) -> None:
            collected.append(piece)

        async def create_stream(*_args: object, **_kwargs: object) -> object:
            return _async_chunks(*chunks)

        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create_stream)),
            close=mock.AsyncMock(),
        )
        with (
            mock.patch("app.skills.llm.AsyncOpenAI", return_value=client),
            mock.patch(
                "app.skills.llm.get_current_llm_config",
                new=mock.AsyncMock(return_value=_runtime_config()),
            ),
            mock.patch(
                "app.skills.llm.LLMUsageService.record_usage",
                new=mock.AsyncMock(),
            ),
        ):
            result = await TenderLLMClient().extract(
                "测试标书原文",
                SEED_PARSE_TEMPLATE,
                on_delta=collect,
            )

        self.assertEqual(result.project_name, "测试项目")
        self.assertEqual("".join(collected), payload)


class SseHelperTests(unittest.IsolatedAsyncioTestCase):
    def test_sse_event_format(self) -> None:
        line = sse_event({"type": "delta", "content": "你好"})
        self.assertTrue(line.startswith("data: "))
        self.assertTrue(line.endswith("\n\n"))
        self.assertIn("你好", line)

    async def test_event_bridge_pump_forwards_until_task_done(self) -> None:
        bridge = EventBridge()

        async def worker() -> str:
            await bridge.emit_stage("llm", "开始")
            await bridge.emit_delta("片段")
            return "ok"

        task = asyncio.create_task(worker())
        events = [event async for event in bridge.pump(task)]
        self.assertEqual(events[0]["type"], "stage")
        self.assertEqual(events[0]["stage"], "llm")
        self.assertEqual(events[1]["type"], "delta")
        self.assertEqual(events[1]["content"], "片段")


def _bad_request() -> BadRequestError:
    return BadRequestError(
        "bad request",
        response=SimpleNamespace(status_code=400, headers={}, request=None),
        body=None,
    )


async def _async_chunks(*chunks: SimpleNamespace) -> object:
    for chunk in chunks:
        yield chunk


if __name__ == "__main__":
    unittest.main()

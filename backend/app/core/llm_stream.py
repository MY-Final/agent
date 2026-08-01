"""LLM 流式事件上下文钩子。

Agent 节点 → 解析服务 → LLM 客户端的调用链很长，逐层传参容易漏。
这里用 ContextVar 挂载可选的增量/阶段回调：流式端点设置钩子后，
深层代码直接读取并上报，非流式调用完全不受影响。
"""

from collections.abc import Awaitable, Callable
from contextvars import ContextVar, Token
from typing import Any

DeltaCallback = Callable[[str], Awaitable[None]]
StageCallback = Callable[[str, str], Awaitable[None]]

LLM_DELTA_CALLBACK: ContextVar[DeltaCallback | None] = ContextVar(
    "llm_delta_callback",
    default=None,
)
PARSE_STAGE_CALLBACK: ContextVar[StageCallback | None] = ContextVar(
    "parse_stage_callback",
    default=None,
)


def set_llm_stream_handlers(
    delta: DeltaCallback | None,
    stage: StageCallback | None,
) -> tuple[Token[Any], Token[Any]]:
    """设置本上下文内的流式回调，返回用于恢复的 Token。"""

    return (
        LLM_DELTA_CALLBACK.set(delta),
        PARSE_STAGE_CALLBACK.set(stage),
    )


def reset_llm_stream_handlers(
    tokens: tuple[Token[Any], Token[Any]],
) -> None:
    """恢复调用前的上下文回调状态。"""

    LLM_DELTA_CALLBACK.reset(tokens[0])
    PARSE_STAGE_CALLBACK.reset(tokens[1])

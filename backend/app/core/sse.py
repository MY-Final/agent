"""SSE（Server-Sent Events）流式输出辅助。"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from app.core.exceptions import AppException

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def sse_event(event: dict[str, Any]) -> str:
    """把事件对象编码成一条 SSE 消息。"""

    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def stream_error_message(exc: Exception) -> tuple[int, str]:
    """把任意异常转成 SSE error 事件的 code + message。"""

    if isinstance(exc, AppException):
        return exc.code, exc.message
    message = str(exc).strip()
    return 50000, (message[:3900] if message else "未知错误")


class EventBridge:
    """把异步回调产生的事件转发为 SSE 数据流。

    用法：创建桥，把 emit_delta / emit_stage 挂到流式上下文钩子上，
    把耗时任务放进 asyncio.create_task，再用 pump 消费事件并实时转发。
    """

    def __init__(self) -> None:
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def emit(self, event: dict[str, Any]) -> None:
        await self._queue.put(event)

    async def emit_stage(self, stage: str, message: str) -> None:
        await self.emit({"type": "stage", "stage": stage, "message": message})

    async def emit_delta(self, content: str) -> None:
        await self.emit({"type": "delta", "content": content})

    async def pump(
        self,
        task: asyncio.Task[Any],
    ) -> AsyncIterator[dict[str, Any]]:
        """持续转发事件，直到 task 完成并清空队列。"""

        while True:
            try:
                yield await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                if task.done():
                    while True:
                        try:
                            yield self._queue.get_nowait()
                        except asyncio.QueueEmpty:
                            return

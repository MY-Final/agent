import asyncio
import io
import uuid
from collections.abc import AsyncIterator
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.llm_stream import reset_llm_stream_handlers, set_llm_stream_handlers
from app.core.minio import minio_storage
from app.core.response import ApiResponse, success_response
from app.core.sse import SSE_HEADERS, EventBridge, sse_event, stream_error_message
from app.models.parse_result import TaskParseResult
from app.schemas.skills.match import MatchInput, MatchResultRead
from app.schemas.skills.parse import (
    ParseInput,
    ParseResultRead,
    ParseResultUpdate,
    ParseSourceTextItem,
)
from app.services.match_service import MatchService
from app.services.parse_service import ParseService
from app.services.export_service import ExportService


router = APIRouter(tags=["业务 Skills"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.post(
    "/skills/parse/stream",
    response_model=None,
    summary="流式调用标书解析 Skill（SSE）",
)
async def parse_skill_stream(
    payload: ParseInput,
    session: SessionDep,
) -> StreamingResponse:
    """SSE 事件流：stage（阶段）/ delta（大模型增量）/ result / error。"""

    async def event_source() -> AsyncIterator[str]:
        bridge = EventBridge()
        tokens = set_llm_stream_handlers(bridge.emit_delta, bridge.emit_stage)
        task: asyncio.Task[TaskParseResult] | None = None
        try:
            await bridge.emit_stage("prepare", "正在准备解析任务…")
            await bridge.emit_stage("extract", "正在提取标书文本…")
            task = asyncio.create_task(
                ParseService.parse_from_input(session, minio_storage, payload)
            )
            async for event in bridge.pump(task):
                yield sse_event(event)
            record = task.result()
            await bridge.emit_stage("done", "解析完成")
            yield sse_event(
                {
                    "type": "result",
                    "data": ParseResultRead.from_orm_record(record).model_dump(
                        mode="json"
                    ),
                }
            )
        except Exception as exc:
            code, message = stream_error_message(exc)
            yield sse_event({"type": "error", "code": code, "message": message})
        finally:
            if task is not None and not task.done():
                task.cancel()
            reset_llm_stream_handlers(tokens)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post(
    "/skills/parse",
    response_model=ApiResponse[ParseResultRead],
    summary="独立调用标书解析 Skill",
)
async def parse_skill(
    payload: ParseInput,
    session: SessionDep,
) -> ApiResponse[ParseResultRead]:
    record = await ParseService.parse_from_input(session, minio_storage, payload)
    return success_response(
        ParseResultRead.from_orm_record(record),
        msg="标书解析成功",
    )


@router.post(
    "/tasks/{task_id}/parse",
    response_model=ApiResponse[ParseResultRead],
    summary="解析任务下的标书文件",
)
async def parse_task(
    task_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[ParseResultRead]:
    record = await ParseService.parse_task(session, minio_storage, task_id)
    return success_response(
        ParseResultRead.from_orm_record(record),
        msg="任务标书解析成功",
    )


@router.get(
    "/tasks/{task_id}/parse-result",
    response_model=ApiResponse[ParseResultRead],
    summary="获取任务最新解析结果",
)
async def get_parse_result(
    task_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[ParseResultRead]:
    record = await ParseService.get_latest_result(session, task_id)
    return success_response(ParseResultRead.from_orm_record(record))


@router.get(
    "/tasks/{task_id}/parse-results",
    response_model=ApiResponse[list[ParseResultRead]],
    summary="获取任务解析历史（多模板版本共存）",
)
async def list_parse_results(
    task_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[list[ParseResultRead]]:
    records = await ParseService.list_results(session, task_id)
    return success_response(
        [ParseResultRead.from_orm_record(record) for record in records]
    )


@router.put(
    "/tasks/{task_id}/parse-results/{parse_result_id}",
    response_model=ApiResponse[ParseResultRead],
    summary="就地修正解析结果字段",
)
async def update_parse_result(
    task_id: uuid.UUID,
    parse_result_id: uuid.UUID,
    payload: ParseResultUpdate,
    session: SessionDep,
) -> ApiResponse[ParseResultRead]:
    record = await ParseService.update_result(
        session,
        task_id,
        parse_result_id,
        payload,
    )
    return success_response(
        ParseResultRead.from_orm_record(record),
        msg="解析结果已修正",
    )


@router.get(
    "/tasks/{task_id}/parse-results/{parse_result_id}/source-text",
    response_model=ApiResponse[list[ParseSourceTextItem]],
    summary="获取解析结果的标书原文文本（人工对照用）",
)
async def get_parse_source_text(
    task_id: uuid.UUID,
    parse_result_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[list[ParseSourceTextItem]]:
    items = await ParseService.get_source_text(session, task_id, parse_result_id)
    return success_response(items)


@router.post(
    "/skills/match",
    response_model=ApiResponse[MatchResultRead],
    summary="独立调用资质匹配 Skill",
)
async def match_skill(
    payload: MatchInput,
    session: SessionDep,
) -> ApiResponse[MatchResultRead]:
    record = await MatchService.match_from_input(session, payload)
    return success_response(
        MatchResultRead.from_orm_record(record),
        msg="资质匹配成功",
    )


@router.post(
    "/tasks/{task_id}/match",
    response_model=ApiResponse[MatchResultRead],
    summary="匹配任务资格要求",
)
async def match_task(
    task_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[MatchResultRead]:
    record = await MatchService.match_task(session, task_id)
    return success_response(
        MatchResultRead.from_orm_record(record),
        msg="任务资质匹配成功",
    )


@router.get(
    "/tasks/{task_id}/match-result",
    response_model=ApiResponse[MatchResultRead],
    summary="获取任务最新资质匹配结果",
)
async def get_match_result(
    task_id: uuid.UUID,
    session: SessionDep,
) -> ApiResponse[MatchResultRead]:
    record = await MatchService.get_latest_result(session, task_id)
    return success_response(MatchResultRead.from_orm_record(record))


@router.get(
    "/tasks/{task_id}/export",
    summary="导出投标分析报告（xlsx）",
)
async def export_task_report(
    task_id: uuid.UUID,
    session: SessionDep,
) -> StreamingResponse:
    filename, content = await ExportService.build_xlsx(session, task_id)
    encoded = quote(filename)
    return StreamingResponse(
        io.BytesIO(content),
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"
        },
    )

from typing import Any, TypedDict


class AgentState(TypedDict):
    """在 LangGraph checkpoint 中持久化的最小流程状态。"""

    agent_run_id: str
    task_id: str
    current_step: str
    parse_result_id: str | None
    match_result_id: str | None
    error_message: str | None
    user_confirmed: bool
    confirmation_note: str | None
    extra: dict[str, Any]


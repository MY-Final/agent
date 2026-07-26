import logging
from contextlib import AbstractAsyncContextManager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.nodes import end_node, human_confirm_node, match_node, parse_node
from app.agent.state import AgentState
from app.core.config import settings


logger = logging.getLogger(__name__)


def build_agent_graph(checkpointer: AsyncPostgresSaver) -> CompiledStateGraph:
    builder = StateGraph(AgentState)
    builder.add_node("parse", parse_node)
    builder.add_node("human_confirm", human_confirm_node)
    builder.add_node("match", match_node)
    builder.add_node("end", end_node)

    builder.add_edge(START, "parse")
    builder.add_conditional_edges(
        "parse",
        _route_after_node,
        {"continue": "human_confirm", "failed": END},
    )
    builder.add_edge("human_confirm", "match")
    builder.add_conditional_edges(
        "match",
        _route_after_node,
        {"continue": "end", "failed": END},
    )
    builder.add_edge("end", END)
    return builder.compile(checkpointer=checkpointer, name="tender-analysis-agent")


def _route_after_node(state: AgentState) -> str:
    return "failed" if state["current_step"] == "failed" else "continue"


class AgentGraphManager:
    """在 FastAPI lifespan 内保持 PostgreSQL checkpointer 连接。"""

    def __init__(self) -> None:
        self._context: AbstractAsyncContextManager[AsyncPostgresSaver] | None = None
        self._checkpointer: AsyncPostgresSaver | None = None
        self._graph: CompiledStateGraph | None = None

    @property
    def graph(self) -> CompiledStateGraph:
        if self._graph is None:
            raise RuntimeError("Agent Graph 尚未初始化")
        return self._graph

    async def connect(self) -> None:
        if self._graph is not None:
            return

        context = AsyncPostgresSaver.from_conn_string(
            settings.langgraph_database_url
        )
        checkpointer = await context.__aenter__()
        try:
            await checkpointer.setup()
            self._context = context
            self._checkpointer = checkpointer
            self._graph = build_agent_graph(checkpointer)
            logger.info("LangGraph PostgreSQL checkpoint 初始化完成")
        except Exception:
            await context.__aexit__(None, None, None)
            raise

    async def disconnect(self) -> None:
        context = self._context
        self._graph = None
        self._checkpointer = None
        self._context = None
        if context is not None:
            await context.__aexit__(None, None, None)

    async def delete_thread(self, thread_id: str) -> None:
        if self._checkpointer is None:
            raise RuntimeError("Agent checkpointer 尚未初始化")
        await self._checkpointer.adelete_thread(thread_id)


agent_graph_manager = AgentGraphManager()

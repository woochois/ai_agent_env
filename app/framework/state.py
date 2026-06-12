"""Supervisor Agent의 LangGraph 상태 정의.

설계 참고: klid-aicb의 ``supervisor_agent/state.py``.
"""

from __future__ import annotations

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class SupervisorInputState(TypedDict):
    """Supervisor 입력 상태."""

    query: str


class SupervisorState(TypedDict):
    """Supervisor의 전체 상태.

    - ``messages``: 대화 메시지 히스토리 (LangGraph add_messages reducer).
    - ``query``: 사용자 질문.
    - ``data``: Tool 실행 결과 데이터 캐시 (data_id 기반).
    """

    messages: Annotated[list, add_messages]
    query: str
    data: dict[str, dict[str, Any]]

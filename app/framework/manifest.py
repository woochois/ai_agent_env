"""Agent 매니페스트 - 각 Tool Agent의 메타데이터 정의.

AI Ops 레이어가 에이전트를 카탈로그화/분류/관리하는 데 사용합니다.
프레임워크 내 다른 모듈에 의존하지 않습니다 (순환 import 방지).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

#: 난이도 등급.
Complexity = str  # "simple" | "medium" | "advanced"


@dataclass(frozen=True)
class AgentManifest:
    """Tool Agent의 메타데이터.

    Attributes:
        agent_type: Agent 타입 식별자 (예: "sql_formatter_agent").
        display_name: 사람이 읽는 이름.
        category: 분류 (예: "SQL", "Schema", "Performance", "Data Quality").
        complexity: 난이도 ("simple" | "medium" | "advanced").
        summary: 한 줄 요약.
        tags: 검색/필터용 태그.
        requires: 외부 의존성 (예: ["postgresql"]). 비어 있으면 순수 로직.
        version: 에이전트 버전.
    """

    agent_type: str
    display_name: str
    category: str = "General"
    complexity: Complexity = "simple"
    summary: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    requires: tuple[str, ...] = field(default_factory=tuple)
    version: str = "1.0.0"

    def to_dict(self) -> dict:
        data = asdict(self)
        data["tags"] = list(self.tags)
        data["requires"] = list(self.requires)
        return data

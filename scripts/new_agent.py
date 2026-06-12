#!/usr/bin/env python3
"""AI Agent 스캐폴딩 CLI.

새 Tool Agent를 빠르게 양산하기 위한 도구입니다. 규약을 따르는 패키지 골격을
``app/tool_agents/<name>/`` 에 생성하면, 프레임워크 레지스트리가 자동으로 발견하여
별도 등록 없이 즉시 사용할 수 있습니다.

사용법:
    python scripts/new_agent.py <agent_name> [--description "설명"]

예:
    python scripts/new_agent.py weather --description "날씨 정보를 조회합니다"

생성 결과:
    app/tool_agents/weather_agent/
    ├── __init__.py
    ├── tool.py        # WeatherTool (BaseAgentTool)
    ├── factory.py     # WeatherAgentFactory + get_factory()
    └── README.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 프로젝트 루트 (이 스크립트의 상위 디렉토리)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOL_AGENTS_DIR = PROJECT_ROOT / "app" / "tool_agents"


def to_snake(name: str) -> str:
    """이름을 snake_case로 정규화합니다 (약어/연속 대문자 처리 포함)."""
    name = re.sub(r"[\s\-]+", "_", name.strip())
    # 약어 경계 처리: "SQLQuery" → "SQL_Query"
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    # 일반 camelCase 경계: "myAgent" → "my_Agent"
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return re.sub(r"_+", "_", name).lower().strip("_")


def to_pascal(snake: str) -> str:
    """snake_case를 PascalCase로 변환합니다."""
    return "".join(part.capitalize() for part in snake.split("_"))


def render_tool_py(agent_type: str, class_prefix: str, tool_name: str) -> str:
    return f'''"""{class_prefix} Agent Tool 구현.

TODO: 실제 비즈니스 로직을 _execute()에 구현하세요.
"""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from app.framework.base import BaseAgentTool, auto_error_artifact, build_artifact

AGENT_TYPE = "{agent_type}"


class {class_prefix}ToolInput(BaseModel):
    """{class_prefix} Tool 입력 스키마."""

    query: str = Field(..., description="입력 값")


class {class_prefix}Tool(BaseAgentTool):
    """{class_prefix} Tool."""

    name: str = "{tool_name}"
    description: str = "TODO: 이 도구가 무엇을 하는지 LLM이 이해할 수 있게 설명하세요."
    args_schema: type[BaseModel] = {class_prefix}ToolInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    def _run(self, query: str, config: RunnableConfig | None = None):
        return self._execute(query)

    async def _arun(self, query: str, config: RunnableConfig | None = None):
        return self._execute(query)

    @auto_error_artifact(
        agent_type=AGENT_TYPE,
        default_message="{class_prefix} 실행 중 오류가 발생했습니다",
    )
    def _execute(self, query: str) -> tuple[str, dict]:
        # TODO: 실제 로직 구현
        result = f"처리됨: {{query}}"
        artifact = build_artifact(AGENT_TYPE, result=result)
        return result, artifact

    def format_content(self, message: ToolMessage) -> ToolMessage:
        """artifact를 LLM 전달용 텍스트로 변환합니다."""
        if isinstance(message.artifact, dict) and "error_message" not in message.artifact:
            result = message.artifact.get("result", "")
            return message.model_copy(update={{"content": str(result)}})
        return message
'''


def render_factory_py(agent_type: str, class_prefix: str, tool_name: str) -> str:
    return f'''"""{class_prefix} Agent 팩토리.

레지스트리 규약: get_factory() -> BaseToolFactory 를 노출합니다.
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseToolFactory
from app.tool_agents.{agent_type}.tool import AGENT_TYPE, {class_prefix}Tool


class {class_prefix}Factory(BaseToolFactory):
    """{class_prefix}Tool을 생성하는 팩토리."""

    agent_type = AGENT_TYPE

    def create_tool(self, tool_config: dict[str, Any]) -> {class_prefix}Tool:
        return {class_prefix}Tool(
            name=tool_config.get("name", "{tool_name}"),
            description=tool_config.get(
                "description", "TODO: 도구 설명"
            ),
        )

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        # TODO: 이 도구의 사용 조건을 Supervisor에게 안내하는 프롬프트
        return "- {tool_name}: TODO 사용 조건을 작성하세요."


def get_factory() -> {class_prefix}Factory:
    """레지스트리가 호출하는 팩토리 진입점."""
    return {class_prefix}Factory()
'''


def render_readme(agent_type: str, class_prefix: str, description: str) -> str:
    return f"""# {class_prefix} Agent

{description or "TODO: 이 Tool Agent의 역할을 설명하세요."}

## 입출력
- **입력**: `query: str` — TODO
- **출력 artifact**: `{{"type": "{agent_type}", "result": ...}}`

## 활성화 (tool_agents config)
```json
{{
  "{class_prefix.lower()}": {{
    "type": "{agent_type}",
    "name": "{agent_type.replace('_agent', '')}",
    "description": "TODO: 도구 설명"
  }}
}}
```

## TODO
- [ ] `tool.py`의 `_execute()`에 실제 로직 구현
- [ ] `factory.py`의 `generate_tool_prompt()`에 사용 안내 작성
- [ ] 테스트 작성 (`tests/test_{agent_type}.py`)
"""


def render_init(class_prefix: str, description: str) -> str:
    return f'''"""{class_prefix} Agent.

{description or "TODO: 설명"}
"""
'''


def create_agent(name: str, description: str) -> Path:
    """Tool Agent 스캐폴딩을 생성합니다.

    Args:
        name: 에이전트 이름 (예: "weather" 또는 "weather_agent").
        description: README/docstring에 들어갈 설명.

    Returns:
        생성된 에이전트 디렉토리 경로.

    Raises:
        FileExistsError: 동일 이름의 에이전트가 이미 존재하는 경우.
    """
    base = to_snake(name)
    if not base:
        raise ValueError("유효한 에이전트 이름을 입력하세요")
    agent_type = base if base.endswith("_agent") else f"{base}_agent"
    class_prefix = to_pascal(agent_type.removesuffix("_agent"))
    tool_name = agent_type.removesuffix("_agent")

    agent_dir = TOOL_AGENTS_DIR / agent_type
    if agent_dir.exists():
        raise FileExistsError(f"이미 존재하는 에이전트입니다: {agent_dir}")

    agent_dir.mkdir(parents=True)
    (agent_dir / "__init__.py").write_text(
        render_init(class_prefix, description), encoding="utf-8"
    )
    (agent_dir / "tool.py").write_text(
        render_tool_py(agent_type, class_prefix, tool_name), encoding="utf-8"
    )
    (agent_dir / "factory.py").write_text(
        render_factory_py(agent_type, class_prefix, tool_name), encoding="utf-8"
    )
    (agent_dir / "README.md").write_text(
        render_readme(agent_type, class_prefix, description), encoding="utf-8"
    )
    return agent_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="새 Tool Agent 스캐폴딩을 생성합니다."
    )
    parser.add_argument("name", help="에이전트 이름 (예: weather, sql_query)")
    parser.add_argument(
        "--description", "-d", default="", help="에이전트 설명"
    )
    args = parser.parse_args(argv)

    try:
        agent_dir = create_agent(args.name, args.description)
    except (FileExistsError, ValueError) as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 1

    rel = agent_dir.relative_to(PROJECT_ROOT)
    print(f"✅ Tool Agent 생성 완료: {rel}/")
    for f in sorted(agent_dir.iterdir()):
        print(f"   - {f.relative_to(PROJECT_ROOT)}")
    print()
    print("다음 단계:")
    print(f"   1. {rel}/tool.py 의 _execute()에 로직을 구현하세요")
    print(f"   2. {rel}/factory.py 의 generate_tool_prompt()를 작성하세요")
    print("   3. 자동 발견됩니다 — GET /agent/supervisor/agents 로 확인하세요")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

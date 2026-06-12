"""스캐폴딩 CLI(scripts/new_agent.py) 테스트.

생성된 에이전트가 규약을 따르고, 레지스트리에 의해 자동 발견되는지 검증합니다.
테스트 후 생성된 디렉토리는 정리합니다.
"""

from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import new_agent  # noqa: E402


def test_to_snake():
    assert new_agent.to_snake("Weather Forecast") == "weather_forecast"
    assert new_agent.to_snake("SQLQuery") == "sql_query"
    assert new_agent.to_snake("my-agent") == "my_agent"


def test_to_pascal():
    assert new_agent.to_pascal("weather_forecast") == "WeatherForecast"
    assert new_agent.to_pascal("sql") == "Sql"


@pytest.fixture
def cleanup_agent():
    created: list[Path] = []
    yield created
    for path in created:
        if path.exists():
            shutil.rmtree(path)


def test_create_agent_generates_files(cleanup_agent):
    agent_dir = new_agent.create_agent("test_scaffold", "테스트용 에이전트")
    cleanup_agent.append(agent_dir)

    assert agent_dir.name == "test_scaffold_agent"
    assert (agent_dir / "__init__.py").exists()
    assert (agent_dir / "tool.py").exists()
    assert (agent_dir / "factory.py").exists()
    assert (agent_dir / "README.md").exists()


def test_create_agent_rejects_duplicate(cleanup_agent):
    agent_dir = new_agent.create_agent("dup_check", "")
    cleanup_agent.append(agent_dir)
    with pytest.raises(FileExistsError):
        new_agent.create_agent("dup_check", "")


def test_scaffolded_agent_is_auto_discovered(cleanup_agent):
    """생성된 에이전트가 레지스트리에 자동 발견되고 Tool을 생성할 수 있다."""
    agent_dir = new_agent.create_agent("autodisc", "자동 발견 테스트")
    cleanup_agent.append(agent_dir)

    # 새로 생성된 패키지를 인식하도록 tool_agents 패키지 캐시 무효화
    import app.tool_agents

    importlib.reload(app.tool_agents)

    from app.framework.registry import ToolAgentRegistry

    reg = ToolAgentRegistry()
    reg.discover(force=True)
    assert "autodisc_agent" in reg.available_types()

    factory = reg.get_factory("autodisc_agent")
    tool = factory.create_tool({"type": "autodisc_agent", "name": "autodisc"})
    assert tool.name == "autodisc"

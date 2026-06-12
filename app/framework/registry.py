"""Tool Agent 자동 등록 레지스트리 및 동적 팩토리.

이 모듈은 AI Agent "양산"의 핵심입니다. ``app/tool_agents/`` 하위에 규약을 따르는
패키지를 추가하기만 하면, 레지스트리가 이를 자동으로 발견(auto-discovery)하여
등록합니다. 별도의 DI 컨테이너 수정이나 수동 등록이 필요 없습니다.

규약: 각 Tool Agent 패키지(``app/tool_agents/<name>/``)는 ``factory.py``에서
``get_factory() -> BaseToolFactory`` 함수를 노출해야 합니다.

- ``ToolAgentRegistry``: 패키지를 스캔하여 팩토리를 수집/보관.
- ``DynamicToolFactory``: 등록된 팩토리들로 런타임에 Tool을 생성.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.framework.base import BaseAgentTool, BaseToolFactory

logger = logging.getLogger(__name__)

#: Tool Agent 패키지들이 위치한 기본 패키지 경로.
TOOL_AGENTS_PACKAGE = "app.tool_agents"


class ToolAgentRegistry:
    """Tool Agent 팩토리를 자동 발견하고 보관하는 레지스트리.

    ``discover()``를 호출하면 ``TOOL_AGENTS_PACKAGE`` 하위의 모든 서브패키지를
    스캔하여, 각 패키지의 ``factory.get_factory()``를 호출해 팩토리를 수집합니다.

    멱등성: 여러 번 호출해도 동일한 결과를 보장합니다 (재스캔 시 초기화).
    """

    def __init__(self, package: str = TOOL_AGENTS_PACKAGE) -> None:
        self._package = package
        self._factories: dict[str, BaseToolFactory] = {}
        self._discovered = False

    def register(self, factory: BaseToolFactory) -> None:
        """팩토리를 수동으로 등록합니다 (테스트 또는 명시적 등록용)."""
        agent_type = factory.agent_type
        if not agent_type:
            raise ValueError(
                f"팩토리 {factory.__class__.__name__}에 agent_type이 지정되지 않았습니다"
            )
        if agent_type in self._factories:
            logger.debug("Tool Agent '%s' 팩토리를 덮어씁니다", agent_type)
        self._factories[agent_type] = factory
        logger.info("Tool Agent 등록됨: %s", agent_type)

    def discover(self, *, force: bool = False) -> dict[str, BaseToolFactory]:
        """Tool Agent 패키지를 스캔하여 팩토리를 자동 등록합니다.

        Args:
            force: True면 이미 스캔했어도 다시 스캔합니다.

        Returns:
            ``{agent_type: factory}`` 매핑.
        """
        if self._discovered and not force:
            return dict(self._factories)

        self._factories.clear()

        try:
            package = importlib.import_module(self._package)
        except ImportError:
            logger.warning("Tool Agent 패키지를 찾을 수 없습니다: %s", self._package)
            self._discovered = True
            return {}

        for module_info in pkgutil.iter_modules(package.__path__):
            if not module_info.ispkg:
                continue
            agent_name = module_info.name
            factory = self._load_factory(agent_name)
            if factory is not None:
                self.register(factory)

        self._discovered = True
        logger.info(
            "Tool Agent 자동 발견 완료: %d개 (%s)",
            len(self._factories),
            ", ".join(sorted(self._factories)) or "없음",
        )
        return dict(self._factories)

    def _load_factory(self, agent_name: str) -> BaseToolFactory | None:
        """단일 Tool Agent 패키지에서 팩토리를 로드합니다."""
        factory_module_path = f"{self._package}.{agent_name}.factory"
        try:
            module = importlib.import_module(factory_module_path)
        except ImportError as exc:
            logger.warning(
                "Tool Agent '%s' 팩토리 모듈 로드 실패: %s", agent_name, exc
            )
            return None

        get_factory = getattr(module, "get_factory", None)
        if get_factory is None:
            logger.warning(
                "Tool Agent '%s'에 get_factory()가 없어 건너뜁니다", agent_name
            )
            return None

        try:
            factory = get_factory()
        except Exception as exc:  # noqa: BLE001 - 개별 에이전트 실패가 전체를 막지 않도록
            logger.error(
                "Tool Agent '%s' 팩토리 생성 실패: %s", agent_name, exc
            )
            return None

        if not isinstance(factory, BaseToolFactory):
            logger.warning(
                "Tool Agent '%s'의 get_factory()가 BaseToolFactory를 반환하지 않습니다",
                agent_name,
            )
            return None
        return factory

    @property
    def factories(self) -> list[BaseToolFactory]:
        """등록된 모든 팩토리 목록."""
        return list(self._factories.values())

    def available_types(self) -> list[str]:
        """등록된 모든 Tool Agent 타입 목록."""
        return sorted(self._factories)

    def get_factory(self, agent_type: str) -> BaseToolFactory | None:
        """타입으로 팩토리를 조회합니다."""
        return self._factories.get(agent_type)


class DynamicToolFactory:
    """등록된 팩토리들을 사용해 런타임에 Tool을 동적 생성하는 팩토리.

    Supervisor는 RunnableConfig의 ``configurable.tool_agents`` 설정을 읽어
    이 팩토리로 활성화된 Tool 목록을 생성합니다.
    """

    def __init__(self, registry: ToolAgentRegistry) -> None:
        self._registry = registry

    def create_tool(self, tool_config: dict[str, Any]) -> BaseAgentTool:
        """tool_config를 기반으로 Tool 인스턴스를 생성합니다.

        Args:
            tool_config: ``{"type", "name", "description", ...}`` 형태의 설정.

        Returns:
            생성된 BaseAgentTool 인스턴스.

        Raises:
            ValueError: 알 수 없는 tool type인 경우.
        """
        tool_type = tool_config.get("type")
        if not tool_type:
            raise ValueError("tool_config에 'type' 필드가 필요합니다")

        for factory in self._registry.factories:
            if factory.is_target_tool(tool_type):
                return factory.create_tool(tool_config)
        raise ValueError(
            f"알 수 없는 Tool Agent 타입: '{tool_type}'. "
            f"사용 가능: {self._registry.available_types()}"
        )

    def create_tools(self, tool_agents: dict[str, dict[str, Any]]) -> list[BaseAgentTool]:
        """여러 tool_config로부터 Tool 목록을 생성합니다.

        Args:
            tool_agents: ``{tool_key: tool_config}`` 매핑.

        Returns:
            생성된 Tool 인스턴스 목록.
        """
        return [self.create_tool(cfg) for cfg in tool_agents.values()]

    async def generate_tool_prompt(self, config: RunnableConfig) -> str:
        """활성화된 Tool들의 사용법 프롬프트를 조합하여 반환합니다."""
        tool_agents: dict = config.get("configurable", {}).get("tool_agents", {})
        prompt_parts: list[str] = []
        for agent_cfg in tool_agents.values():
            agent_type = agent_cfg.get("type")
            for factory in self._registry.factories:
                if factory.is_target_tool(agent_type):
                    part = await factory.generate_tool_prompt(config)
                    if part:
                        prompt_parts.append(part)
                    break
        return "\n\n".join(prompt_parts)


#: 애플리케이션 전역에서 공유하는 기본 레지스트리 인스턴스.
registry = ToolAgentRegistry()

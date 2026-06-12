"""AI Ops - 모든 Agent를 한 곳에서 관리/모니터링하는 운영 레이어.

레지스트리(자동 발견된 매니페스트)와 메트릭 수집기를 결합하여 다음을 제공합니다.
- 에이전트 카탈로그 (분류/난이도/의존성/태그)
- 실행 메트릭 (호출 수, 에러율, 평균 지연)
- 활성/비활성 토글 (운영 중 특정 에이전트 차단)
- 헬스 요약 (에러율 기반 상태 평가)
"""

from __future__ import annotations

import logging

from app.framework.metrics import MetricsCollector, metrics
from app.framework.registry import ToolAgentRegistry, registry

logger = logging.getLogger(__name__)

#: 헬스 평가 임계값 (에러율).
_DEGRADED_ERROR_RATE = 0.2
_UNHEALTHY_ERROR_RATE = 0.5


class AgentOpsService:
    """Agent 운영 관리 서비스.

    레지스트리와 메트릭을 결합하여 카탈로그/상태/제어 기능을 제공합니다.
    비활성화 상태는 인메모리로 관리됩니다 (프로세스 생명주기 동안 유지).
    """

    def __init__(
        self,
        agent_registry: ToolAgentRegistry,
        metrics_collector: MetricsCollector,
    ) -> None:
        self._registry = agent_registry
        self._metrics = metrics_collector
        self._disabled: set[str] = set()

    # --- 카탈로그 ---

    def catalog(self) -> list[dict]:
        """등록된 모든 Agent의 매니페스트 + 상태 + 메트릭 요약을 반환합니다."""
        self._registry.discover()
        items = []
        for factory in self._registry.factories:
            manifest = factory.get_manifest()
            items.append(self._build_entry(manifest))
        return sorted(items, key=lambda x: (x["category"], x["agent_type"]))

    def get_agent(self, agent_type: str) -> dict | None:
        """단일 Agent의 상세 정보를 반환합니다 (없으면 None)."""
        self._registry.discover()
        factory = self._registry.get_factory(agent_type)
        if factory is None:
            return None
        return self._build_entry(factory.get_manifest(), detailed=True)

    def _build_entry(self, manifest, detailed: bool = False) -> dict:
        entry = manifest.to_dict()
        entry["enabled"] = manifest.agent_type not in self._disabled
        metric = self._metrics.get(manifest.agent_type)
        entry["metrics"] = metric.to_dict() if metric else None
        entry["health"] = self._evaluate_health(metric)
        return entry

    # --- 메트릭 ---

    def metrics_summary(self) -> dict:
        """전체 메트릭 집계 요약을 반환합니다."""
        all_metrics = self._metrics.all()
        total_invocations = sum(m.invocations for m in all_metrics.values())
        total_failures = sum(m.failures for m in all_metrics.values())
        return {
            "total_agents_with_activity": len(all_metrics),
            "total_invocations": total_invocations,
            "total_failures": total_failures,
            "overall_error_rate": round(
                total_failures / total_invocations, 4
            ) if total_invocations else 0.0,
            "per_agent": {k: v.to_dict() for k, v in all_metrics.items()},
        }

    def reset_metrics(self, agent_type: str | None = None) -> None:
        """메트릭을 초기화합니다."""
        self._metrics.reset(agent_type)

    # --- 활성/비활성 제어 ---

    def set_enabled(self, agent_type: str, enabled: bool) -> bool:
        """Agent를 활성/비활성화합니다.

        Returns:
            성공 여부 (등록되지 않은 agent_type이면 False).
        """
        self._registry.discover()
        if self._registry.get_factory(agent_type) is None:
            return False
        if enabled:
            self._disabled.discard(agent_type)
        else:
            self._disabled.add(agent_type)
        logger.info("Agent '%s' %s", agent_type, "활성화" if enabled else "비활성화")
        return True

    def is_enabled(self, agent_type: str) -> bool:
        """Agent 활성 여부를 반환합니다."""
        return agent_type not in self._disabled

    def filter_enabled(self, tool_agents: dict[str, dict]) -> dict[str, dict]:
        """tool_agents 설정에서 비활성화된 Agent를 제거합니다.

        Supervisor 실행 전 호출하여 운영자가 끈 Agent가 사용되지 않도록 합니다.
        """
        return {
            key: cfg
            for key, cfg in tool_agents.items()
            if cfg.get("type") not in self._disabled
        }

    # --- 헬스 ---

    def health(self) -> dict:
        """전체 Agent 헬스 요약을 반환합니다."""
        catalog = self.catalog()
        statuses = [c["health"]["status"] for c in catalog]
        if any(s == "unhealthy" for s in statuses):
            overall = "unhealthy"
        elif any(s == "degraded" for s in statuses):
            overall = "degraded"
        else:
            overall = "healthy"
        return {
            "overall": overall,
            "total_agents": len(catalog),
            "enabled": sum(1 for c in catalog if c["enabled"]),
            "disabled": sum(1 for c in catalog if not c["enabled"]),
            "by_category": self._count_by_category(catalog),
        }

    def _evaluate_health(self, metric) -> dict:
        """단일 Agent의 헬스를 에러율 기반으로 평가합니다."""
        if metric is None or metric.invocations == 0:
            return {"status": "idle", "reason": "호출 이력 없음"}
        rate = metric.error_rate
        if rate >= _UNHEALTHY_ERROR_RATE:
            status = "unhealthy"
        elif rate >= _DEGRADED_ERROR_RATE:
            status = "degraded"
        else:
            status = "healthy"
        return {"status": status, "error_rate": round(rate, 4)}

    @staticmethod
    def _count_by_category(catalog: list[dict]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in catalog:
            counts[entry["category"]] = counts.get(entry["category"], 0) + 1
        return counts


#: 애플리케이션 전역 Ops 서비스.
ops_service = AgentOpsService(registry, metrics)

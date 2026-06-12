"""Agent 실행 메트릭 수집기.

각 Tool Agent의 호출 횟수, 성공/실패 수, 누적/평균 지연 시간을 인메모리로
집계합니다. AI Ops 레이어가 이 데이터를 조회하여 에이전트 상태를 모니터링합니다.

이 모듈은 프레임워크 내 다른 모듈에 의존하지 않습니다 (순환 import 방지).
``app/framework/base.py``의 ``auto_error_artifact`` 데코레이터가 여기에 기록합니다.
"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field


@dataclass
class AgentMetric:
    """단일 Agent의 누적 실행 메트릭."""

    agent_type: str
    invocations: int = 0
    successes: int = 0
    failures: int = 0
    total_duration_ms: float = 0.0
    last_invoked_at: float | None = None
    last_error: str | None = None

    @property
    def avg_duration_ms(self) -> float:
        """평균 실행 시간(ms). 호출이 없으면 0."""
        return self.total_duration_ms / self.invocations if self.invocations else 0.0

    @property
    def error_rate(self) -> float:
        """에러율 (0.0 ~ 1.0). 호출이 없으면 0."""
        return self.failures / self.invocations if self.invocations else 0.0

    def to_dict(self) -> dict:
        data = asdict(self)
        data["avg_duration_ms"] = round(self.avg_duration_ms, 3)
        data["error_rate"] = round(self.error_rate, 4)
        return data


class MetricsCollector:
    """스레드 안전한 Agent 메트릭 집계기."""

    def __init__(self) -> None:
        self._metrics: dict[str, AgentMetric] = {}
        self._lock = threading.Lock()

    def record(
        self,
        agent_type: str,
        *,
        success: bool,
        duration_ms: float,
        error: str | None = None,
    ) -> None:
        """단일 실행 결과를 기록합니다.

        Args:
            agent_type: Agent 타입 식별자.
            success: 성공 여부.
            duration_ms: 실행 소요 시간(ms).
            error: 실패 시 에러 메시지(선택).
        """
        with self._lock:
            metric = self._metrics.setdefault(agent_type, AgentMetric(agent_type))
            metric.invocations += 1
            metric.total_duration_ms += duration_ms
            metric.last_invoked_at = time.time()
            if success:
                metric.successes += 1
            else:
                metric.failures += 1
                metric.last_error = error

    def get(self, agent_type: str) -> AgentMetric | None:
        """특정 Agent의 메트릭을 반환합니다 (없으면 None)."""
        with self._lock:
            metric = self._metrics.get(agent_type)
            return _copy(metric) if metric else None

    def all(self) -> dict[str, AgentMetric]:
        """모든 Agent의 메트릭 스냅샷을 반환합니다."""
        with self._lock:
            return {k: _copy(v) for k, v in self._metrics.items()}

    def reset(self, agent_type: str | None = None) -> None:
        """메트릭을 초기화합니다 (agent_type 미지정 시 전체)."""
        with self._lock:
            if agent_type is None:
                self._metrics.clear()
            else:
                self._metrics.pop(agent_type, None)


def _copy(metric: AgentMetric) -> AgentMetric:
    """메트릭의 얕은 복사본을 반환합니다 (외부 변경 방지)."""
    return AgentMetric(**{k: v for k, v in asdict(metric).items()})


#: 애플리케이션 전역 메트릭 수집기.
metrics = MetricsCollector()

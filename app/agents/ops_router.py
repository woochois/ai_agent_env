"""AI Ops FastAPI 라우터.

모든 Agent를 한 곳에서 관리/모니터링하는 운영 API와 대시보드를 제공합니다.

엔드포인트:
    GET  /ops/agents                    - 에이전트 카탈로그 (분류/난이도/메트릭)
    GET  /ops/agents/{agent_type}       - 단일 에이전트 상세
    POST /ops/agents/{agent_type}/enable  - 활성화
    POST /ops/agents/{agent_type}/disable - 비활성화
    GET  /ops/metrics                   - 메트릭 집계 요약
    POST /ops/metrics/reset             - 메트릭 초기화
    GET  /ops/health                    - 전체 헬스 요약
    GET  /ops/dashboard                 - HTML 대시보드
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.framework.ops import ops_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/agents")
async def list_agents() -> dict:
    """등록된 모든 Agent의 카탈로그를 반환합니다."""
    catalog = ops_service.catalog()
    return {"agents": catalog, "count": len(catalog)}


@router.get("/agents/{agent_type}")
async def get_agent(agent_type: str) -> dict:
    """단일 Agent의 상세 정보를 반환합니다."""
    entry = ops_service.get_agent(agent_type)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Agent를 찾을 수 없습니다: {agent_type}")
    return entry


@router.post("/agents/{agent_type}/enable")
async def enable_agent(agent_type: str) -> dict:
    """Agent를 활성화합니다."""
    if not ops_service.set_enabled(agent_type, True):
        raise HTTPException(status_code=404, detail=f"Agent를 찾을 수 없습니다: {agent_type}")
    return {"agent_type": agent_type, "enabled": True}


@router.post("/agents/{agent_type}/disable")
async def disable_agent(agent_type: str) -> dict:
    """Agent를 비활성화합니다."""
    if not ops_service.set_enabled(agent_type, False):
        raise HTTPException(status_code=404, detail=f"Agent를 찾을 수 없습니다: {agent_type}")
    return {"agent_type": agent_type, "enabled": False}


@router.get("/metrics")
async def get_metrics() -> dict:
    """전체 메트릭 집계 요약을 반환합니다."""
    return ops_service.metrics_summary()


@router.post("/metrics/reset")
async def reset_metrics(agent_type: str | None = None) -> dict:
    """메트릭을 초기화합니다 (agent_type 미지정 시 전체)."""
    ops_service.reset_metrics(agent_type)
    return {"reset": agent_type or "all"}


@router.get("/health")
async def ops_health() -> dict:
    """전체 Agent 헬스 요약을 반환합니다."""
    return ops_service.health()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> str:
    """간단한 HTML 운영 대시보드를 반환합니다."""
    return _DASHBOARD_HTML


_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>AI Ops Dashboard</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           margin: 0; background: #0f1115; color: #e6e6e6; }
    header { padding: 20px 28px; background: #161a22; border-bottom: 1px solid #262b36; }
    h1 { margin: 0; font-size: 20px; }
    .sub { color: #8a93a6; font-size: 13px; margin-top: 4px; }
    .summary { display: flex; gap: 16px; padding: 20px 28px; flex-wrap: wrap; }
    .card { background: #161a22; border: 1px solid #262b36; border-radius: 10px;
            padding: 16px 20px; min-width: 130px; }
    .card .n { font-size: 26px; font-weight: 600; }
    .card .l { color: #8a93a6; font-size: 12px; margin-top: 4px; }
    table { width: calc(100% - 56px); margin: 8px 28px 28px; border-collapse: collapse;
            background: #161a22; border-radius: 10px; overflow: hidden; }
    th, td { text-align: left; padding: 10px 14px; border-bottom: 1px solid #262b36; font-size: 13px; }
    th { color: #8a93a6; font-weight: 500; background: #1b2029; }
    .badge { padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; }
    .simple { background:#1e3a2f; color:#6ee7a8; } .medium { background:#3a341e; color:#e7d36e; }
    .advanced { background:#3a1e2a; color:#e76e9b; }
    .healthy { color:#6ee7a8; } .degraded { color:#e7d36e; } .unhealthy { color:#e76e9b; } .idle { color:#8a93a6; }
    button { background:#2a3140; color:#e6e6e6; border:1px solid #3a4150; border-radius:6px;
             padding:4px 10px; cursor:pointer; font-size:12px; }
    button:hover { background:#333b4d; }
    .off { opacity: 0.45; }
  </style>
</head>
<body>
  <header>
    <h1>AI Ops Dashboard</h1>
    <div class="sub">모든 Agent를 한 곳에서 관리/모니터링합니다 · 5초마다 자동 갱신</div>
  </header>
  <div class="summary" id="summary"></div>
  <table id="tbl">
    <thead><tr>
      <th>Agent</th><th>분류</th><th>난이도</th><th>의존성</th>
      <th>호출</th><th>에러율</th><th>평균(ms)</th><th>헬스</th><th>제어</th>
    </tr></thead>
    <tbody id="rows"></tbody>
  </table>
  <script>
    async function load() {
      const [cat, health] = await Promise.all([
        fetch('/ops/agents').then(r=>r.json()),
        fetch('/ops/health').then(r=>r.json()),
      ]);
      const s = document.getElementById('summary');
      s.innerHTML = `
        <div class="card"><div class="n">${health.total_agents}</div><div class="l">전체 Agent</div></div>
        <div class="card"><div class="n">${health.enabled}</div><div class="l">활성</div></div>
        <div class="card"><div class="n">${health.disabled}</div><div class="l">비활성</div></div>
        <div class="card"><div class="n ${health.overall}">${health.overall}</div><div class="l">전체 헬스</div></div>
      `;
      const rows = document.getElementById('rows');
      rows.innerHTML = cat.agents.map(a => {
        const m = a.metrics || {};
        const h = a.health || {};
        const er = m.error_rate != null ? (m.error_rate*100).toFixed(1)+'%' : '-';
        const av = m.avg_duration_ms != null ? m.avg_duration_ms.toFixed(1) : '-';
        const toggle = a.enabled
          ? `<button onclick="toggle('${a.agent_type}', false)">비활성화</button>`
          : `<button onclick="toggle('${a.agent_type}', true)">활성화</button>`;
        return `<tr class="${a.enabled ? '' : 'off'}">
          <td><b>${a.display_name}</b><br/><span class="l" style="color:#8a93a6">${a.agent_type}</span></td>
          <td>${a.category}</td>
          <td><span class="badge ${a.complexity}">${a.complexity}</span></td>
          <td>${(a.requires||[]).join(', ') || '-'}</td>
          <td>${m.invocations || 0}</td>
          <td>${er}</td>
          <td>${av}</td>
          <td class="${h.status}">${h.status || 'idle'}</td>
          <td>${toggle}</td>
        </tr>`;
      }).join('');
    }
    async function toggle(type, enable) {
      await fetch(`/ops/agents/${type}/${enable ? 'enable' : 'disable'}`, {method:'POST'});
      load();
    }
    load();
    setInterval(load, 5000);
  </script>
</body>
</html>
"""

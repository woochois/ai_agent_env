"""비즈니스 Tool Agent 통합 테스트.

LLM 호출을 mock하여 각 에이전트의 정합성을 검증합니다:
1. Input 스키마 유효성
2. Tool 인스턴스 생성
3. _arun() 실행 (mock LLM 응답)
4. artifact 구조 검증
5. format_content() 검증
6. 에러 처리 (auto_error_artifact) 검증
"""

import asyncio
import json
import sys
import os
import warnings

warnings.filterwarnings("ignore")

# 환경 변수 세팅 (config.py 검증 우회)
os.environ.setdefault("OPENAI_API_KEY", "test-key-for-unit-test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("ELASTICSEARCH_URL", "http://localhost:9200")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import AsyncMock, patch, MagicMock
from langchain_core.messages import ToolMessage


# ============================================================
# Mock LLM 응답 데이터
# ============================================================

MOCK_RESPONSES = {
    "email_draft_agent": json.dumps({
        "subject": "프로젝트 진행 현황 보고",
        "body": "김팀장님께,\n\n안녕하세요. 프로젝트 진행 현황을 말씀드립니다.\n\n현재 Phase 1이 90% 완료되었으며, 다음 주 월요일까지 마무리될 예정입니다.\n\n감사합니다.\n홍길동 드림"
    }),
    "meeting_summary_agent": json.dumps({
        "title": "주간 팀 회의",
        "attendees": ["김팀장", "이과장", "박대리"],
        "agenda": ["프로젝트 진행 현황", "다음 주 계획"],
        "decisions": ["Phase 1 마감일 연장 (3일)", "QA 인력 추가 투입"],
        "action_items": [
            {"assignee": "이과장", "task": "QA 일정 재수립", "deadline": "금요일"},
            {"assignee": "박대리", "task": "테스트 케이스 작성", "deadline": "수요일"}
        ]
    }),
    "report_outline_agent": json.dumps({
        "topic": "디지털 트랜스포메이션 전략",
        "purpose": "경영진 보고",
        "outline_sections": [
            {"title": "개요", "key_points": ["현황 분석", "목표 설정"], "subsections": []},
            {"title": "추진 전략", "key_points": ["단계별 로드맵", "투자 계획"], "subsections": [
                {"title": "Phase 1: 인프라", "key_points": ["클라우드 마이그레이션"]}
            ]},
            {"title": "기대 효과", "key_points": ["비용 절감 30%", "생산성 향상"], "subsections": []}
        ]
    }),
    "schedule_planner_agent": json.dumps({
        "tasks": [
            {"name": "기획서 작성", "estimated_hours": 8, "deadline": "2024-01-15", "priority": "high"},
            {"name": "디자인 리뷰", "estimated_hours": 2, "deadline": "2024-01-16", "priority": "medium"}
        ],
        "schedule": [
            {"date": "2024-01-13", "tasks": ["기획서 작성"]},
            {"date": "2024-01-14", "tasks": ["기획서 작성", "디자인 리뷰"]}
        ],
        "priorities": ["high: 기획서 작성", "medium: 디자인 리뷰"]
    }),
    "translation_agent": json.dumps({
        "source_text": "분기별 매출 실적 보고서",
        "translated_text": "Quarterly Revenue Performance Report",
        "source_lang": "ko",
        "target_lang": "en",
        "domain": "finance"
    }),
    "document_review_agent": json.dumps({
        "issues": [
            {"category": "grammar", "location": "1번째 문단", "description": "주어 누락"}
        ],
        "suggestions": [
            {"original": "진행 중이다", "revised": "진행 중입니다", "reason": "경어체 통일"}
        ],
        "overall_score": 7,
        "doc_type": "report"
    }),
    "data_insight_agent": json.dumps({
        "insights": ["1분기 매출이 전년 대비 15% 증가", "신규 고객 유입률 상승"],
        "trends": ["매출 우상향 추세 지속", "계절 변동성 감소"],
        "anomalies": ["3월 급격한 반품률 증가 (평균의 3배)"],
        "recommendations": ["3월 이상치 원인 조사 필요", "신규 고객 유지율 개선 전략 수립"],
        "perspective": "sales"
    }),
    "task_breakdown_agent": json.dumps({
        "project_name": "사내 포털 리뉴얼",
        "tasks": [
            {"task_name": "요구사항 분석", "description": "이해관계자 인터뷰", "estimated_hours": 16, "priority": "high", "dependencies": []},
            {"task_name": "UI 설계", "description": "와이어프레임 작성", "estimated_hours": 24, "priority": "high", "dependencies": ["요구사항 분석"]}
        ],
        "dependencies": [["요구사항 분석", "UI 설계"]],
        "total_estimated_hours": 40
    }),
    "regulation_check_agent": json.dumps({
        "query": "연차 사용 절차",
        "regulations": [
            {"title": "근로기준법", "article": "제60조", "content": "1년간 80% 이상 출근 시 15일 연차 부여"}
        ],
        "summary": "연차는 최소 1일 전 신청하며, 부서장 승인 후 사용 가능합니다.",
        "cautions": ["긴급 연차는 사후 승인 가능", "연속 5일 이상 사용 시 2주 전 신청"],
        "disclaimer": "본 답변은 일반적인 안내이며, 정확한 규정은 인사팀에 확인하시기 바랍니다."
    }),
    "presentation_helper_agent": json.dumps({
        "topic": "AI 도입 전략",
        "audience": "경영진",
        "duration_minutes": 15,
        "slides": [
            {"slide_number": 1, "title": "AI 도입 필요성", "key_points": ["시장 동향", "경쟁사 현황"], "script": "안녕하세요, 오늘은 AI 도입 전략에 대해 말씀드리겠습니다."},
            {"slide_number": 2, "title": "추진 계획", "key_points": ["3단계 로드맵", "예산"], "script": "추진 계획은 3단계로 나뉩니다."}
        ]
    }),
}

# ============================================================
# 테스트 설정
# ============================================================

AGENT_TEST_CONFIGS = [
    {
        "name": "email_draft_agent",
        "module": "app.tool_agents.email_draft_agent.tool",
        "tool_class": "EmailDraftTool",
        "input_kwargs": {"purpose": "프로젝트 현황 보고", "recipient": "김팀장", "key_points": "Phase 1 90% 완료, 다음주 마감", "tone": "formal", "language": "ko"},
        "artifact_required_keys": ["type", "subject", "body", "tone", "language"],
    },
    {
        "name": "meeting_summary_agent",
        "module": "app.tool_agents.meeting_summary_agent.tool",
        "tool_class": "MeetingSummaryTool",
        "input_kwargs": {"content": "참석: 김팀장, 이과장, 박대리. 안건: 프로젝트 진행현황. 결정: Phase1 마감 3일 연장. 액션: 이과장-QA일정 재수립(금요일)", "meeting_title": "주간 팀 회의"},
        "artifact_required_keys": ["type", "title", "attendees", "agenda", "decisions", "action_items"],
    },
    {
        "name": "report_outline_agent",
        "module": "app.tool_agents.report_outline_agent.tool",
        "tool_class": "ReportOutlineTool",
        "input_kwargs": {"topic": "디지털 트랜스포메이션", "purpose": "경영진 보고", "audience": "executive"},
        "artifact_required_keys": ["type", "topic", "purpose", "outline_sections"],
    },
    {
        "name": "schedule_planner_agent",
        "module": "app.tool_agents.schedule_planner_agent.tool",
        "tool_class": "SchedulePlannerTool",
        "input_kwargs": {"tasks": "기획서 작성 8시간 마감 1/15, 디자인 리뷰 2시간 마감 1/16", "start_date": "2024-01-13"},
        "artifact_required_keys": ["type", "tasks", "schedule", "priorities"],
    },
    {
        "name": "translation_agent",
        "module": "app.tool_agents.translation_agent.tool",
        "tool_class": "TranslationTool",
        "input_kwargs": {"text": "분기별 매출 실적 보고서", "target_lang": "en", "domain": "finance"},
        "artifact_required_keys": ["type", "source_text", "translated_text", "source_lang", "target_lang", "domain"],
    },
    {
        "name": "document_review_agent",
        "module": "app.tool_agents.document_review_agent.tool",
        "tool_class": "DocumentReviewTool",
        "input_kwargs": {"document": "프로젝트 진행 중이다. 현재 Phase 1 완료되었고 Phase 2 시작할 예정.", "doc_type": "report"},
        "artifact_required_keys": ["type", "issues", "suggestions", "overall_score"],
    },
    {
        "name": "data_insight_agent",
        "module": "app.tool_agents.data_insight_agent.tool",
        "tool_class": "DataInsightTool",
        "input_kwargs": {"data": "월,매출\n1월,100\n2월,120\n3월,95\n4월,140", "perspective": "sales"},
        "artifact_required_keys": ["type", "insights", "trends", "anomalies", "recommendations"],
    },
    {
        "name": "task_breakdown_agent",
        "module": "app.tool_agents.task_breakdown_agent.tool",
        "tool_class": "TaskBreakdownTool",
        "input_kwargs": {"project": "사내 포털 리뉴얼", "goal": "UX 개선 및 모바일 대응", "constraints": "3개월 내 완료"},
        "artifact_required_keys": ["type", "project_name", "tasks", "dependencies", "total_estimated_hours"],
    },
    {
        "name": "regulation_check_agent",
        "module": "app.tool_agents.regulation_check_agent.tool",
        "tool_class": "RegulationCheckTool",
        "input_kwargs": {"query": "연차 사용 절차가 어떻게 되나요?", "category": "hr"},
        "artifact_required_keys": ["type", "query", "regulations", "summary", "cautions"],
    },
    {
        "name": "presentation_helper_agent",
        "module": "app.tool_agents.presentation_helper_agent.tool",
        "tool_class": "PresentationHelperTool",
        "input_kwargs": {"topic": "AI 도입 전략", "audience": "경영진", "duration_minutes": 15},
        "artifact_required_keys": ["type", "topic", "audience", "slides"],
    },
]


# ============================================================
# 테스트 실행
# ============================================================

async def test_agent(config: dict) -> dict:
    """단일 에이전트를 테스트합니다."""
    name = config["name"]
    result = {"name": name, "tests": {}}

    try:
        # 1. Import 검증
        import importlib
        mod = importlib.import_module(config["module"])
        ToolClass = getattr(mod, config["tool_class"])
        result["tests"]["import"] = "✅ PASS"
    except Exception as e:
        result["tests"]["import"] = f"❌ FAIL: {e}"
        return result

    try:
        # 2. Tool 인스턴스 생성
        tool = ToolClass()
        result["tests"]["instantiation"] = "✅ PASS"
    except Exception as e:
        result["tests"]["instantiation"] = f"❌ FAIL: {e}"
        return result

    # 3. _arun() 실행 (mock LLM)
    try:
        mock_response = MOCK_RESPONSES[name]
        # patch at the module where call_llm is used (each tool.py imports it)
        patch_target = f"{config['module']}.call_llm"
        with patch(patch_target, new_callable=AsyncMock, return_value=mock_response):
            content, artifact = await tool._arun(**config["input_kwargs"])

        assert isinstance(content, str) and len(content) > 0, "content가 비어있음"
        assert isinstance(artifact, dict), "artifact가 dict가 아님"
        result["tests"]["arun_execution"] = "✅ PASS"
    except Exception as e:
        result["tests"]["arun_execution"] = f"❌ FAIL: {e}"
        return result

    # 4. Artifact 필수 키 검증
    try:
        missing_keys = [k for k in config["artifact_required_keys"] if k not in artifact]
        assert not missing_keys, f"누락된 키: {missing_keys}"
        assert artifact["type"] == name, f"type 불일치: {artifact['type']} != {name}"
        result["tests"]["artifact_structure"] = "✅ PASS"
    except Exception as e:
        result["tests"]["artifact_structure"] = f"❌ FAIL: {e}"

    # 5. format_content() 검증
    try:
        msg = ToolMessage(content=content, tool_call_id="test", artifact=artifact)
        formatted = tool.format_content(msg)
        assert isinstance(formatted.content, str) and len(formatted.content) > 0
        result["tests"]["format_content"] = "✅ PASS"
    except Exception as e:
        result["tests"]["format_content"] = f"❌ FAIL: {e}"

    # 6. 에러 처리 검증 (LLM 에러 시 auto_error_artifact)
    try:
        patch_target = f"{config['module']}.call_llm"
        with patch(patch_target, new_callable=AsyncMock, side_effect=RuntimeError("API 연결 실패")):
            err_content, err_artifact = await tool._arun(**config["input_kwargs"])
        assert "error_message" in err_artifact, "에러 artifact에 error_message 없음"
        assert err_artifact["type"] == name
        result["tests"]["error_handling"] = "✅ PASS"
    except Exception as e:
        result["tests"]["error_handling"] = f"❌ FAIL: {e}"

    return result


async def run_all_tests():
    """모든 에이전트 테스트를 실행합니다."""
    print("=" * 60)
    print("  비즈니스 Tool Agent 통합 테스트")
    print("=" * 60)
    print()

    total_pass = 0
    total_fail = 0
    results = []

    for config in AGENT_TEST_CONFIGS:
        result = await test_agent(config)
        results.append(result)

        print(f"📦 {result['name']}")
        for test_name, status in result["tests"].items():
            print(f"   {test_name}: {status}")
            if "✅" in status:
                total_pass += 1
            else:
                total_fail += 1
        print()

    print("=" * 60)
    print(f"  결과: {total_pass} PASS / {total_fail} FAIL / {total_pass + total_fail} TOTAL")
    print("=" * 60)

    return total_fail == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)

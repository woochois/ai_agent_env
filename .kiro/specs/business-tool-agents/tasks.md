# Implementation Tasks

## Task 1: 공통 유틸리티 모듈 생성

- [x] 1.1 `app/tool_agents/_llm_utils.py` 파일 생성: `parse_json_response()` 헬퍼 함수 구현 (LLM 응답에서 JSON 블록 추출 및 파싱)
- [x] 1.2 `app/tool_agents/_llm_utils.py`에 `call_llm()` 비동기 헬퍼 함수 구현: `create_chat_model()` + 시스템/유저 메시지 구성 + `ainvoke()` 호출을 래핑

## Task 2: email_draft_agent 구현

- [x] 2.1 `app/tool_agents/email_draft_agent/__init__.py` 생성 (빈 파일)
- [x] 2.2 `app/tool_agents/email_draft_agent/tool.py` 구현: `EmailDraftInput` 스키마(purpose, recipient, key_points, tone, language), `EmailDraftTool` 클래스 (_arun에서 LLM 호출, 이메일 초안 생성, artifact 반환)
- [x] 2.3 `app/tool_agents/email_draft_agent/factory.py` 구현: `EmailDraftFactory` 클래스 (agent_type, 메타데이터, create_tool, generate_tool_prompt, get_factory)

## Task 3: meeting_summary_agent 구현

- [x] 3.1 `app/tool_agents/meeting_summary_agent/__init__.py` 생성 (빈 파일)
- [x] 3.2 `app/tool_agents/meeting_summary_agent/tool.py` 구현: `MeetingSummaryInput` 스키마(content, meeting_title), `MeetingSummaryTool` 클래스 (_arun에서 회의록 구조화 추출)
- [x] 3.3 `app/tool_agents/meeting_summary_agent/factory.py` 구현: `MeetingSummaryFactory` 클래스

## Task 4: report_outline_agent 구현

- [x] 4.1 `app/tool_agents/report_outline_agent/__init__.py` 생성 (빈 파일)
- [x] 4.2 `app/tool_agents/report_outline_agent/tool.py` 구현: `ReportOutlineInput` 스키마(topic, purpose, audience), `ReportOutlineTool` 클래스
- [x] 4.3 `app/tool_agents/report_outline_agent/factory.py` 구현: `ReportOutlineFactory` 클래스

## Task 5: schedule_planner_agent 구현

- [x] 5.1 `app/tool_agents/schedule_planner_agent/__init__.py` 생성 (빈 파일)
- [x] 5.2 `app/tool_agents/schedule_planner_agent/tool.py` 구현: `SchedulePlannerInput` 스키마(tasks, start_date), `SchedulePlannerTool` 클래스
- [x] 5.3 `app/tool_agents/schedule_planner_agent/factory.py` 구현: `SchedulePlannerFactory` 클래스

## Task 6: translation_agent 구현

- [x] 6.1 `app/tool_agents/translation_agent/__init__.py` 생성 (빈 파일)
- [x] 6.2 `app/tool_agents/translation_agent/tool.py` 구현: `TranslationInput` 스키마(text, target_lang, domain), `TranslationTool` 클래스 (언어 자동 감지, 도메인 전문 용어 반영)
- [x] 6.3 `app/tool_agents/translation_agent/factory.py` 구현: `TranslationFactory` 클래스

## Task 7: document_review_agent 구현

- [x] 7.1 `app/tool_agents/document_review_agent/__init__.py` 생성 (빈 파일)
- [x] 7.2 `app/tool_agents/document_review_agent/tool.py` 구현: `DocumentReviewInput` 스키마(document, doc_type), `DocumentReviewTool` 클래스 (문법/일관성/논리적 흐름 분석, 점수화)
- [x] 7.3 `app/tool_agents/document_review_agent/factory.py` 구현: `DocumentReviewFactory` 클래스

## Task 8: data_insight_agent 구현

- [x] 8.1 `app/tool_agents/data_insight_agent/__init__.py` 생성 (빈 파일)
- [x] 8.2 `app/tool_agents/data_insight_agent/tool.py` 구현: `DataInsightInput` 스키마(data, perspective), `DataInsightTool` 클래스 (데이터 패턴/이상치/트렌드 분석)
- [x] 8.3 `app/tool_agents/data_insight_agent/factory.py` 구현: `DataInsightFactory` 클래스

## Task 9: task_breakdown_agent 구현

- [x] 9.1 `app/tool_agents/task_breakdown_agent/__init__.py` 생성 (빈 파일)
- [x] 9.2 `app/tool_agents/task_breakdown_agent/tool.py` 구현: `TaskBreakdownInput` 스키마(project, goal, constraints), `TaskBreakdownTool` 클래스 (WBS, 의존관계, 소요시간 추정)
- [x] 9.3 `app/tool_agents/task_breakdown_agent/factory.py` 구현: `TaskBreakdownFactory` 클래스

## Task 10: regulation_check_agent 구현

- [x] 10.1 `app/tool_agents/regulation_check_agent/__init__.py` 생성 (빈 파일)
- [x] 10.2 `app/tool_agents/regulation_check_agent/tool.py` 구현: `RegulationCheckInput` 스키마(query, category), `RegulationCheckTool` 클래스 (규정 조항/주의사항/면책조항 포함)
- [x] 10.3 `app/tool_agents/regulation_check_agent/factory.py` 구현: `RegulationCheckFactory` 클래스

## Task 11: presentation_helper_agent 구현

- [x] 11.1 `app/tool_agents/presentation_helper_agent/__init__.py` 생성 (빈 파일)
- [x] 11.2 `app/tool_agents/presentation_helper_agent/tool.py` 구현: `PresentationHelperInput` 스키마(topic, audience, duration_minutes), `PresentationHelperTool` 클래스 (슬라이드 구성, 스크립트 생성)
- [x] 11.3 `app/tool_agents/presentation_helper_agent/factory.py` 구현: `PresentationHelperFactory` 클래스

## Task 12: 통합 검증

- [x] 12.1 Registry 자동 등록 테스트: Python에서 `registry.discover(force=True)` 실행하여 10개 새 에이전트 + 기존 에이전트 모두 정상 등록 확인
- [x] 12.2 각 에이전트 import 검증: `from app.tool_agents.{agent_name}.factory import get_factory` 호출 성공 확인

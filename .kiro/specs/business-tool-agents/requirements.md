# Requirements Document

## Introduction

일반 회사원의 업무 생산성을 높이기 위한 10개의 비즈니스 Tool Agent를 구현합니다. 각 에이전트는 기존 `ai_agent_env` 프레임워크의 `BaseAgentTool` / `BaseToolFactory` 패턴을 준수하며, LLM(OpenAI)을 활용하여 이메일 작성, 회의록 요약, 보고서 개요, 일정 계획, 번역, 문서 검토, 데이터 인사이트, 업무 분해, 규정 확인, 발표 자료 구성 등의 업무를 지원합니다.

## Glossary

- **Tool_Agent**: `app/tool_agents/` 하위에 위치하며, `BaseAgentTool`을 상속한 LangChain Tool 구현체
- **Factory**: `BaseToolFactory`를 상속하여 `get_factory()` 진입점을 제공하는 Tool 생성 클래스
- **Artifact**: Tool Agent가 반환하는 `(content: str, artifact: dict)` 튜플 중 구조화된 JSON 결과
- **Registry**: `app/tool_agents/` 하위 패키지를 자동 스캔하여 Factory를 등록하는 시스템
- **LLM**: `create_chat_model()`로 생성되는 OpenAI ChatGPT 기반 언어 모델
- **Supervisor**: Tool Agent들을 오케스트레이션하여 사용자 질문에 답변하는 상위 에이전트
- **EARS_Pattern**: 요구사항 기술 표준 (Ubiquitous, Event-driven, State-driven, Unwanted event, Optional, Complex)

## Requirements

### Requirement 1: 이메일 초안 작성 에이전트 (email_draft_agent)

**User Story:** As a 회사원, I want 목적/수신자/핵심내용을 입력하면 비즈니스 이메일 초안을 생성받고 싶다, so that 이메일 작성 시간을 단축할 수 있다.

#### Acceptance Criteria

1. WHEN 목적, 수신자, 핵심내용이 입력되면, THE Email_Draft_Agent SHALL LLM을 호출하여 인사말, 본문, 마무리를 포함한 비즈니스 이메일 초안을 생성한다
2. WHEN 톤(formal/casual/polite) 옵션이 지정되면, THE Email_Draft_Agent SHALL 해당 톤에 맞는 어투로 이메일을 생성한다
3. WHEN 언어 옵션이 지정되면, THE Email_Draft_Agent SHALL 해당 언어(한국어/영어)로 이메일을 생성한다
4. THE Email_Draft_Agent SHALL `(content, artifact)` 튜플을 반환하며, artifact에는 `type`, `subject`, `body`, `tone`, `language` 필드를 포함한다
5. IF LLM 호출이 실패하면, THEN THE Email_Draft_Agent SHALL `build_error_artifact()`를 사용하여 에러 정보를 반환한다

### Requirement 2: 회의록 요약 에이전트 (meeting_summary_agent)

**User Story:** As a 회사원, I want 회의 내용 텍스트를 입력하면 참석자, 안건, 결정사항, 액션아이템으로 구조화된 회의록 요약을 받고 싶다, so that 회의 후 정리 시간을 줄일 수 있다.

#### Acceptance Criteria

1. WHEN 회의 내용 텍스트가 입력되면, THE Meeting_Summary_Agent SHALL LLM을 호출하여 참석자, 안건, 결정사항, 액션아이템을 추출하고 구조화된 요약을 생성한다
2. THE Meeting_Summary_Agent SHALL artifact에 `type`, `attendees`, `agenda`, `decisions`, `action_items` 필드를 포함한다
3. WHEN 회의 내용에서 참석자 정보를 추출할 수 없으면, THE Meeting_Summary_Agent SHALL attendees 필드를 빈 리스트로 반환한다
4. IF LLM 호출이 실패하면, THEN THE Meeting_Summary_Agent SHALL `build_error_artifact()`를 사용하여 에러 정보를 반환한다

### Requirement 3: 보고서 개요 작성 에이전트 (report_outline_agent)

**User Story:** As a 회사원, I want 주제와 목적을 입력하면 보고서 목차와 섹션별 요점을 제안받고 싶다, so that 보고서 구성에 소요되는 초기 기획 시간을 단축할 수 있다.

#### Acceptance Criteria

1. WHEN 주제와 목적이 입력되면, THE Report_Outline_Agent SHALL LLM을 호출하여 보고서 목차(계층 구조), 각 섹션의 핵심 포인트, 작성 가이드를 생성한다
2. WHEN 대상 독자(audience) 옵션이 지정되면, THE Report_Outline_Agent SHALL 해당 독자 수준에 맞는 내용 깊이와 구성을 반영한다
3. THE Report_Outline_Agent SHALL artifact에 `type`, `topic`, `purpose`, `outline_sections` 필드를 포함하며, `outline_sections`는 title, key_points, subsections를 가진 리스트 구조로 반환한다
4. IF LLM 호출이 실패하면, THEN THE Report_Outline_Agent SHALL `build_error_artifact()`를 사용하여 에러 정보를 반환한다

### Requirement 4: 일정 계획 에이전트 (schedule_planner_agent)

**User Story:** As a 회사원, I want 업무 목록과 마감일을 입력하면 우선순위와 일별 일정 제안을 받고 싶다, so that 효율적으로 업무를 배분할 수 있다.

#### Acceptance Criteria

1. WHEN 업무 목록(업무명, 예상소요시간, 마감일 포함)이 입력되면, THE Schedule_Planner_Agent SHALL LLM을 호출하여 우선순위 배정과 일별 일정표를 생성한다
2. THE Schedule_Planner_Agent SHALL 마감일이 가까운 업무와 소요시간이 긴 업무에 높은 우선순위를 배정한다
3. THE Schedule_Planner_Agent SHALL artifact에 `type`, `tasks`, `schedule`, `priorities` 필드를 포함한다
4. IF LLM 호출이 실패하면, THEN THE Schedule_Planner_Agent SHALL `build_error_artifact()`를 사용하여 에러 정보를 반환한다

### Requirement 5: 비즈니스 번역 에이전트 (translation_agent)

**User Story:** As a 회사원, I want 비즈니스 문서를 한↔영 번역하면서 전문 용어의 일관성과 비즈니스 톤을 유지하고 싶다, so that 전문적인 다국어 문서를 빠르게 생성할 수 있다.

#### Acceptance Criteria

1. WHEN 원문 텍스트와 목표 언어(ko/en)가 입력되면, THE Translation_Agent SHALL LLM을 호출하여 비즈니스 맥락에 적합한 번역을 생성한다
2. WHEN 도메인(finance/legal/tech/general) 옵션이 지정되면, THE Translation_Agent SHALL 해당 도메인의 전문 용어를 반영하여 번역한다
3. THE Translation_Agent SHALL artifact에 `type`, `source_text`, `translated_text`, `source_lang`, `target_lang`, `domain` 필드를 포함한다
4. IF LLM 호출이 실패하면, THEN THE Translation_Agent SHALL `build_error_artifact()`를 사용하여 에러 정보를 반환한다

### Requirement 6: 문서 검토 에이전트 (document_review_agent)

**User Story:** As a 회사원, I want 작성한 문서의 문법, 일관성, 논리적 흐름을 검토받고 개선 제안을 얻고 싶다, so that 문서의 완성도를 높이고 검토 시간을 줄일 수 있다.

#### Acceptance Criteria

1. WHEN 문서 텍스트가 입력되면, THE Document_Review_Agent SHALL LLM을 호출하여 문법 오류, 논리적 일관성, 어조 통일성, 구조적 흐름을 분석하고 개선 제안을 생성한다
2. THE Document_Review_Agent SHALL artifact에 `type`, `issues` (카테고리별 문제점 목록), `suggestions` (구체적 수정 제안), `overall_score` (1-10 점수) 필드를 포함한다
3. WHEN 문서 유형(보고서/기획서/이메일/계약서) 옵션이 지정되면, THE Document_Review_Agent SHALL 해당 문서 유형의 관례와 형식 기준으로 검토한다
4. IF LLM 호출이 실패하면, THEN THE Document_Review_Agent SHALL `build_error_artifact()`를 사용하여 에러 정보를 반환한다

### Requirement 7: 데이터 인사이트 에이전트 (data_insight_agent)

**User Story:** As a 회사원, I want CSV나 표 형태 데이터를 입력하면 핵심 인사이트와 트렌드를 도출받고 싶다, so that 데이터 분석 역량 없이도 데이터 기반 의사결정을 할 수 있다.

#### Acceptance Criteria

1. WHEN CSV 형식 또는 마크다운 테이블 형식의 데이터가 입력되면, THE Data_Insight_Agent SHALL LLM을 호출하여 데이터의 주요 패턴, 이상치, 트렌드를 분석하고 핵심 인사이트를 생성한다
2. THE Data_Insight_Agent SHALL artifact에 `type`, `insights` (핵심 발견사항 리스트), `trends` (트렌드 설명), `anomalies` (이상치 목록), `recommendations` (권장 조치) 필드를 포함한다
3. WHEN 분석 관점(매출/비용/인력/고객) 옵션이 지정되면, THE Data_Insight_Agent SHALL 해당 관점을 중심으로 인사이트를 도출한다
4. IF LLM 호출이 실패하면, THEN THE Data_Insight_Agent SHALL `build_error_artifact()`를 사용하여 에러 정보를 반환한다

### Requirement 8: 업무 분해 에이전트 (task_breakdown_agent)

**User Story:** As a 회사원, I want 대형 프로젝트를 세부 태스크로 분해하고 소요시간을 추정받고 싶다, so that 프로젝트 계획을 체계적으로 수립할 수 있다.

#### Acceptance Criteria

1. WHEN 프로젝트 설명과 목표가 입력되면, THE Task_Breakdown_Agent SHALL LLM을 호출하여 세부 태스크 분해(WBS), 의존 관계, 소요시간 추정을 생성한다
2. THE Task_Breakdown_Agent SHALL artifact에 `type`, `project_name`, `tasks` (태스크 목록), `dependencies` (의존 관계), `total_estimated_hours` 필드를 포함한다
3. THE Task_Breakdown_Agent SHALL 각 태스크에 `task_name`, `description`, `estimated_hours`, `priority`, `dependencies` 필드를 포함한다
4. IF LLM 호출이 실패하면, THEN THE Task_Breakdown_Agent SHALL `build_error_artifact()`를 사용하여 에러 정보를 반환한다

### Requirement 9: 규정 확인 에이전트 (regulation_check_agent)

**User Story:** As a 회사원, I want 업무 관련 질문을 입력하면 관련 규정과 절차를 요약받고 싶다, so that 규정 위반 없이 업무를 처리할 수 있다.

#### Acceptance Criteria

1. WHEN 업무 관련 질문이 입력되면, THE Regulation_Check_Agent SHALL LLM을 호출하여 관련 규정 조항, 적용 범위, 주의사항을 정리하여 반환한다
2. WHEN 규정 유형(인사/재무/보안/구매) 옵션이 지정되면, THE Regulation_Check_Agent SHALL 해당 영역의 규정을 우선적으로 참조하여 답변한다
3. THE Regulation_Check_Agent SHALL artifact에 `type`, `query`, `regulations` (관련 규정 목록), `summary`, `cautions` (주의사항) 필드를 포함한다
4. THE Regulation_Check_Agent SHALL 답변에 항상 면책 조항(disclaimer)을 포함하여 실제 규정 확인을 권고한다
5. IF LLM 호출이 실패하면, THEN THE Regulation_Check_Agent SHALL `build_error_artifact()`를 사용하여 에러 정보를 반환한다

### Requirement 10: 발표 자료 도우미 에이전트 (presentation_helper_agent)

**User Story:** As a 회사원, I want 주제와 대상을 입력하면 발표 슬라이드 구성과 각 슬라이드별 스크립트를 제안받고 싶다, so that 발표 준비 시간을 단축할 수 있다.

#### Acceptance Criteria

1. WHEN 발표 주제와 대상 청중이 입력되면, THE Presentation_Helper_Agent SHALL LLM을 호출하여 슬라이드 구성(제목, 내용 요점)과 각 슬라이드별 발표 스크립트를 생성한다
2. WHEN 발표 시간(분) 옵션이 지정되면, THE Presentation_Helper_Agent SHALL 해당 시간에 맞는 슬라이드 수와 분량을 조절한다
3. THE Presentation_Helper_Agent SHALL artifact에 `type`, `topic`, `audience`, `duration_minutes`, `slides` 필드를 포함하며, 각 slide는 `title`, `key_points`, `script` 필드를 포함한다
4. IF LLM 호출이 실패하면, THEN THE Presentation_Helper_Agent SHALL `build_error_artifact()`를 사용하여 에러 정보를 반환한다

### Requirement 11: 프레임워크 준수

**User Story:** As a 개발자, I want 모든 새 에이전트가 기존 ai_agent_env 프레임워크 규약을 준수하길 원한다, so that 레지스트리 자동 등록과 일관된 운영이 가능하다.

#### Acceptance Criteria

1. THE Tool_Agent SHALL `app/tool_agents/{agent_name}/` 디렉토리에 `__init__.py`, `tool.py`, `factory.py` 파일을 포함한다
2. THE Factory SHALL `factory.py`에서 `get_factory() -> BaseToolFactory` 함수를 노출한다
3. THE Tool_Agent SHALL `BaseAgentTool`을 상속하고, `_arun()` 메서드를 구현한다
4. THE Tool_Agent SHALL `response_format = "content_and_artifact"`를 설정하고, `(content: str, artifact: dict)` 튜플을 반환한다
5. THE Tool_Agent SHALL `auto_error_artifact` 데코레이터를 적용하여 모든 예외를 표준 에러 artifact로 변환한다
6. THE Factory SHALL `agent_type`, `display_name`, `category`, `summary`, `tags` 메타데이터를 선언한다
7. THE Registry SHALL `app/tool_agents/` 하위 패키지를 스캔하여 새 에이전트를 자동 등록한다

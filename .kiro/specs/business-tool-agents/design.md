# Design Document

## Overview

klid-aicb의 에이전트 구조를 분석하여, ai_agent_env 프레임워크에 맞는 10개의 비즈니스 업무용 Tool Agent를 구현합니다. 각 에이전트는 LLM(OpenAI)을 활용하여 구조화된 출력을 생성하며, 기존 프레임워크의 `BaseAgentTool` / `BaseToolFactory` / `auto_error_artifact` 패턴을 정확히 따릅니다.

## Architecture

### 공통 구조 패턴

모든 비즈니스 에이전트는 동일한 아키텍처 패턴을 따릅니다:

```
app/tool_agents/{agent_name}/
├── __init__.py           # 빈 파일
├── tool.py               # BaseAgentTool 상속, _arun() 구현
└── factory.py            # BaseToolFactory 상속, get_factory() 노출
```

### 실행 흐름

```
User Input → Supervisor → DynamicToolFactory → Agent Tool._arun()
                                                    │
                                                    ├─ create_chat_model() → LLM 호출
                                                    ├─ 프롬프트 + 입력 조합
                                                    ├─ LLM 응답 파싱
                                                    └─ (content, artifact) 반환
```

### LLM 호출 전략

모든 비즈니스 에이전트는 다음 패턴으로 LLM을 호출합니다:

1. `create_chat_model()`로 ChatOpenAI 인스턴스 생성
2. 에이전트별 시스템 프롬프트 + 사용자 입력으로 메시지 구성
3. `model.ainvoke(messages)` 비동기 호출
4. 응답에서 구조화된 데이터 추출
5. `build_artifact()` 또는 JSON 파싱으로 artifact 생성

## Component Design

### 1. email_draft_agent

**Input Schema:**
```python
class EmailDraftInput(BaseModel):
    purpose: str          # 이메일 목적
    recipient: str        # 수신자 (이름/직함)
    key_points: str       # 핵심 전달 내용
    tone: str = "formal"  # formal | casual | polite
    language: str = "ko"  # ko | en
```

**Artifact Structure:**
```json
{
  "type": "email_draft_agent",
  "subject": "제안된 제목",
  "body": "이메일 본문 전체",
  "tone": "formal",
  "language": "ko"
}
```

**시스템 프롬프트 전략:** 역할(비즈니스 이메일 전문가), 톤 가이드라인, 구조(인사-본문-마무리) 지시

---

### 2. meeting_summary_agent

**Input Schema:**
```python
class MeetingSummaryInput(BaseModel):
    content: str          # 회의 내용 텍스트 (녹취록, 메모 등)
    meeting_title: str = ""  # 회의 제목 (선택)
```

**Artifact Structure:**
```json
{
  "type": "meeting_summary_agent",
  "title": "회의 제목",
  "attendees": ["참석자1", "참석자2"],
  "agenda": ["안건1", "안건2"],
  "decisions": ["결정사항1", "결정사항2"],
  "action_items": [
    {"assignee": "담당자", "task": "업무내용", "deadline": "마감일"}
  ]
}
```

**시스템 프롬프트 전략:** 회의록 전문 비서 역할, 구조화 추출 지시, JSON 포맷 출력

---

### 3. report_outline_agent

**Input Schema:**
```python
class ReportOutlineInput(BaseModel):
    topic: str            # 보고서 주제
    purpose: str          # 보고서 목적
    audience: str = "general"  # executive | technical | general
```

**Artifact Structure:**
```json
{
  "type": "report_outline_agent",
  "topic": "주제",
  "purpose": "목적",
  "outline_sections": [
    {
      "title": "섹션 제목",
      "key_points": ["요점1", "요점2"],
      "subsections": [
        {"title": "하위 섹션", "key_points": ["세부 요점"]}
      ]
    }
  ]
}
```

---

### 4. schedule_planner_agent

**Input Schema:**
```python
class SchedulePlannerInput(BaseModel):
    tasks: str            # 업무 목록 (텍스트: 업무명, 소요시간, 마감일 포함)
    start_date: str = ""  # 시작일 (선택, YYYY-MM-DD)
```

**Artifact Structure:**
```json
{
  "type": "schedule_planner_agent",
  "tasks": [
    {"name": "업무명", "estimated_hours": 4, "deadline": "2024-01-15", "priority": "high"}
  ],
  "schedule": [
    {"date": "2024-01-10", "tasks": ["업무1", "업무2"]}
  ],
  "priorities": ["high: 업무1", "medium: 업무3"]
}
```

---

### 5. translation_agent

**Input Schema:**
```python
class TranslationInput(BaseModel):
    text: str             # 번역할 원문
    target_lang: str      # "ko" | "en"
    domain: str = "general"  # finance | legal | tech | general
```

**Artifact Structure:**
```json
{
  "type": "translation_agent",
  "source_text": "원문",
  "translated_text": "번역문",
  "source_lang": "en",
  "target_lang": "ko",
  "domain": "finance"
}
```

**시스템 프롬프트 전략:** 전문 번역가 역할, 도메인 용어 일관성 지시, 원문 톤 유지

---

### 6. document_review_agent

**Input Schema:**
```python
class DocumentReviewInput(BaseModel):
    document: str         # 검토할 문서 텍스트
    doc_type: str = "general"  # report | proposal | email | contract | general
```

**Artifact Structure:**
```json
{
  "type": "document_review_agent",
  "issues": [
    {"category": "grammar", "location": "2번째 문단", "description": "주어-서술어 불일치"}
  ],
  "suggestions": [
    {"original": "원문 부분", "revised": "수정 제안", "reason": "이유"}
  ],
  "overall_score": 7,
  "doc_type": "report"
}
```

---

### 7. data_insight_agent

**Input Schema:**
```python
class DataInsightInput(BaseModel):
    data: str             # CSV 또는 마크다운 테이블 형식 데이터
    perspective: str = "general"  # sales | cost | hr | customer | general
```

**Artifact Structure:**
```json
{
  "type": "data_insight_agent",
  "insights": ["핵심 발견1", "핵심 발견2"],
  "trends": ["트렌드1 설명", "트렌드2 설명"],
  "anomalies": ["이상치1 설명"],
  "recommendations": ["권장 조치1", "권장 조치2"],
  "perspective": "sales"
}
```

---

### 8. task_breakdown_agent

**Input Schema:**
```python
class TaskBreakdownInput(BaseModel):
    project: str          # 프로젝트 설명
    goal: str             # 프로젝트 목표
    constraints: str = "" # 제약 조건 (선택)
```

**Artifact Structure:**
```json
{
  "type": "task_breakdown_agent",
  "project_name": "프로젝트명",
  "tasks": [
    {
      "task_name": "태스크명",
      "description": "설명",
      "estimated_hours": 8,
      "priority": "high",
      "dependencies": ["선행 태스크명"]
    }
  ],
  "dependencies": [["태스크A", "태스크B"]],
  "total_estimated_hours": 120
}
```

---

### 9. regulation_check_agent

**Input Schema:**
```python
class RegulationCheckInput(BaseModel):
    query: str            # 규정 관련 질문
    category: str = "general"  # hr | finance | security | procurement | general
```

**Artifact Structure:**
```json
{
  "type": "regulation_check_agent",
  "query": "원본 질문",
  "regulations": [
    {"title": "규정명", "article": "조항", "content": "내용 요약"}
  ],
  "summary": "요약 답변",
  "cautions": ["주의사항1", "주의사항2"],
  "disclaimer": "면책 조항 텍스트"
}
```

---

### 10. presentation_helper_agent

**Input Schema:**
```python
class PresentationHelperInput(BaseModel):
    topic: str            # 발표 주제
    audience: str         # 대상 청중
    duration_minutes: int = 15  # 발표 시간 (분)
```

**Artifact Structure:**
```json
{
  "type": "presentation_helper_agent",
  "topic": "발표 주제",
  "audience": "대상 청중",
  "duration_minutes": 15,
  "slides": [
    {
      "slide_number": 1,
      "title": "슬라이드 제목",
      "key_points": ["요점1", "요점2"],
      "script": "발표 스크립트 텍스트"
    }
  ]
}
```

## Implementation Details

### 공통 LLM 호출 패턴 (모든 에이전트에 적용)

```python
from app.framework.model import create_chat_model
from langchain_core.messages import SystemMessage, HumanMessage

async def _call_llm(system_prompt: str, user_input: str) -> str:
    model = create_chat_model(model="gpt-4o-mini", temperature=0.3)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_input),
    ]
    response = await model.ainvoke(messages)
    return response.content
```

### JSON 파싱 전략

LLM 응답에서 JSON을 추출할 때:
1. 응답에서 ```json ... ``` 블록 파싱 시도
2. 실패 시 전체 응답을 JSON으로 파싱 시도
3. 최종 실패 시 텍스트를 content로 반환하고 최소 artifact 생성

```python
import json
import re

def parse_json_response(response_text: str) -> dict | None:
    # 1. 코드 블록에서 JSON 추출
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response_text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # 2. 전체를 JSON으로 파싱
    try:
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        return None
```

### Factory 메타데이터 설계

| Agent | category | complexity | tags |
|-------|----------|-----------|------|
| email_draft | Communication | simple | (email, draft, writing) |
| meeting_summary | Productivity | simple | (meeting, summary, minutes) |
| report_outline | Documentation | simple | (report, outline, writing) |
| schedule_planner | Productivity | medium | (schedule, planning, priority) |
| translation | Communication | medium | (translation, korean, english) |
| document_review | Documentation | medium | (review, grammar, quality) |
| data_insight | Analytics | medium | (data, analysis, insight) |
| task_breakdown | Project Management | medium | (project, wbs, planning) |
| regulation_check | Compliance | medium | (regulation, compliance, policy) |
| presentation_helper | Communication | medium | (presentation, slides, script) |

### 에러 처리 전략

모든 에이전트의 핵심 로직 메서드에 `@auto_error_artifact` 데코레이터를 적용:

```python
@auto_error_artifact(
    agent_type=AGENT_TYPE,
    default_message="[에이전트명] 실행 중 오류가 발생했습니다",
)
async def _execute(self, ...) -> tuple[str, dict]:
    ...
```

### format_content() 구현 전략

각 에이전트의 `format_content()`는 artifact를 마크다운으로 변환하여 LLM이 읽기 좋은 형태로 전달:

```python
def format_content(self, message: ToolMessage) -> ToolMessage:
    art = message.artifact if isinstance(message.artifact, dict) else {}
    if "error_message" in art:
        return message
    # artifact → 마크다운 변환 로직
    content = self._format_to_markdown(art)
    return message.model_copy(update={"content": content})
```

## Dependencies

- `langchain-core`: BaseModel, BaseTool, messages
- `langchain-openai`: ChatOpenAI (create_chat_model에서 사용)
- `pydantic`: Input schema 정의
- 기존 프레임워크: `app.framework.base`, `app.framework.model`
- 외부 서비스: OpenAI API (OPENAI_API_KEY 환경 변수)

## Testing Strategy

- 각 에이전트의 Input Schema 유효성 검증 (Pydantic 자체 처리)
- `auto_error_artifact` 데코레이터를 통한 에러 처리 검증
- Registry 자동 발견 확인: 에이전트 추가 후 `registry.discover()` 호출 시 등록 확인
- LLM 호출은 모킹하여 단위 테스트 가능하도록 설계 (create_chat_model을 주입 가능하게 구성)

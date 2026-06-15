# AI Agent Ops

데이터베이스 운영을 위한 AI 에이전트 플랫폼. LLM 기반의 Tool Agent들을 조합하여 DB 관련 작업을 자동화합니다.

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Layer                            │
│  /supervisor/chat  /supervisor/chat/stream  /supervisor/pipeline │
└───────────┬──────────────────┬────────────────────┬─────────┘
            │                  │                    │
            ▼                  ▼                    ▼
┌───────────────┐   ┌──────────────┐   ┌─────────────────┐
│ SupervisorSvc │   │ SSE Streamer │   │Pipeline_Executor│
│  (LangGraph)  │   │              │   │                 │
└───────┬───────┘   └──────┬───────┘   └────────┬────────┘
        │                   │                    │
        ▼                   ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                     Model_Router                             │
│  ┌──────────┐ ┌───────────┐ ┌─────────┐ ┌────────┐        │
│  │  OpenAI  │ │ Anthropic │ │ Google  │ │ Local  │        │
│  │ Provider │ │ Provider  │ │Provider │ │Provider│        │
│  └──────────┘ └───────────┘ └─────────┘ └────────┘        │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│              Agent_Registry (auto-discovery)                  │
│  ┌────────────┐ ┌──────────────┐ ┌───────────────┐         │
│  │ sql_expert │ │schema_expert │ │communication  │  ...    │
│  └────────────┘ └──────────────┘ └───────────────┘         │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│                      State_Store                             │
│          PostgreSQL (sessions table)                          │
│        fallback → InMemorySaver                              │
└─────────────────────────────────────────────────────────────┘
```

### 핵심 컴포넌트

| 컴포넌트 | 설명 |
|----------|------|
| **Model_Router** | 모델 식별자(예: `anthropic/claude-3`)를 파싱하여 적절한 LLM Provider로 라우팅 |
| **Pipeline_Executor** | 여러 Agent를 순차 체이닝, 이전 스텝 결과를 다음 스텝 입력으로 전달 |
| **State_Store** | 세션 상태를 PostgreSQL에 영속 저장 (폴백: InMemory) |
| **SSE Streamer** | LangGraph astream_events를 SSE 형식으로 실시간 토큰 스트리밍 |
| **Agent_Registry** | Tool Agent 팩토리를 자동 발견/등록하는 플러그인 레지스트리 |

## 빠른 시작

### 1. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일을 열어 실제 값으로 수정
```

### 2-A. Docker로 실행 (권장)

```bash
docker compose up --build
```

서비스가 시작되면:
- **웹 UI**: http://localhost:8000
- **Swagger API 문서**: http://localhost:8000/docs
- **헬스체크**: http://localhost:8000/health

### 2-B. 로컬 실행

```bash
# Python 3.11+ 필요
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 서버 실행
uvicorn app.main:app --reload --port 8000
```

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | 웹 UI |
| GET | `/health` | 헬스체크 |
| GET | `/docs` | Swagger UI (자동 생성) |
| POST | `/agent/chat` | 기본 Agent 대화 |
| POST | `/agent/supervisor/chat` | Supervisor Agent 대화 (Tool Agent 활성화) |
| POST | `/agent/supervisor/chat/stream` | SSE 스트리밍 대화 (실시간 토큰) |
| POST | `/agent/supervisor/pipeline` | Agent Pipeline 순차 실행 |
| GET | `/agent/supervisor/agents` | 등록된 Tool Agent 목록 |

### POST /agent/supervisor/chat/stream

SSE(Server-Sent Events)를 통해 LLM 응답을 토큰 단위로 실시간 스트리밍합니다.

**Request Body:**
```json
{
  "message": "SELECT * FROM users를 포맷해주세요",
  "tool_agents": [
    {"type": "sql_expert", "name": "sql_expert", "description": "SQL Expert", "config": {}}
  ],
  "session_id": "optional-session-id",
  "system_prompt": "You are a helpful SQL assistant."
}
```

**SSE 이벤트 타입:**
- `token` - LLM 토큰 생성: `{"content": "분석", "timestamp": "2024-01-01T00:00:00Z"}`
- `tool_call` - Tool 호출 시작: `{"agent_type": "sql_expert", "sub_command": "format"}`
- `tool_result` - Tool 결과: `{"artifact": {...}}`
- `done` - 완료: `{"full_response": "...", "session_id": "...", "tool_calls": [...]}`
- `error` - 에러: `{"error_message": "...", "error_type": "llm_error"}`

### POST /agent/supervisor/pipeline

Agent Pipeline을 정의하고 순차 실행합니다. LLM 개입 없이 정해진 순서대로 Agent를 실행합니다.

**Request Body:**
```json
{
  "steps": [
    {"agent_type": "sql_expert", "sub_command": "format", "input_mapping": {}},
    {"agent_type": "sql_expert", "sub_command": "explain", "input_mapping": {"query": "$.formatted_sql"}}
  ],
  "initial_input": {"sql": "select * from users where id = 1"}
}
```

**Response (200):**
```json
{
  "pipeline_id": "uuid-string",
  "steps": [
    {
      "step_index": 0,
      "agent_type": "sql_expert",
      "sub_command": "format",
      "input_data": {"sql": "select * from users where id = 1"},
      "output_artifact": {"formatted_sql": "SELECT *\nFROM users\nWHERE id = 1", "original": "..."},
      "duration_ms": 5.2,
      "status": "success"
    }
  ],
  "total_duration_ms": 12.5,
  "status": "completed"
}
```

**Validation Error (422):**
```json
{
  "errors": ["Unknown agent_types: ['nonexistent']"],
  "trace": {"pipeline_id": "", "steps": [], "total_duration_ms": 0, "status": "validation_error"}
}
```

## Expert Agents (통합 에이전트)

기존 24개 개별 에이전트를 5개 Expert Agent로 통합했습니다. 각 Expert Agent는 `sub_command`를 통해 여러 기능을 단일 진입점으로 제공합니다.

| Expert Agent | Sub Commands | 설명 |
|-------------|-------------|------|
| `sql_expert` | format, lint, explain, analyze_slow_query | SQL 포맷팅, 린트, 실행계획, 슬로우쿼리 분석 |
| `schema_expert` | generate_ddl, inspect_schema, generate_er_diagram, advise_index | DDL 생성, 스키마 조회, ER 다이어그램, 인덱스 추천 |
| `communication` | draft_email, translate, summarize_meeting | 이메일 초안, 번역, 회의록 요약 |
| `document` | review, outline_report, assist_presentation | 문서 리뷰, 보고서 목차, 발표 도우미 |
| `planning` | breakdown_task, plan_schedule | 태스크 분해, 일정 계획 |

### 사용 예시

```python
import httpx

# SQL Expert - format
response = httpx.post("http://localhost:8000/agent/supervisor/chat", json={
    "message": "이 SQL을 포맷해줘: select id,name from users where status='active'",
    "tool_agents": [{"type": "sql_expert", "name": "sql_expert", "description": "SQL Expert", "config": {}}],
})

# Pipeline - format → explain 체이닝
response = httpx.post("http://localhost:8000/agent/supervisor/pipeline", json={
    "steps": [
        {"agent_type": "sql_expert", "sub_command": "format", "input_mapping": {"sql": "$.raw_sql"}},
        {"agent_type": "sql_expert", "sub_command": "explain", "input_mapping": {"query": "$.formatted_sql"}},
    ],
    "initial_input": {"raw_sql": "select * from orders where created_at > '2024-01-01'"}
})
```

## 멀티 모델 지원

Model_Router를 통해 다양한 LLM 프로바이더를 사용할 수 있습니다.

| Provider | 환경 변수 | 모델 식별자 예시 |
|----------|----------|-----------------|
| OpenAI (기본) | `OPENAI_API_KEY` | `gpt-4o`, `gpt-4o-mini` |
| Anthropic | `ANTHROPIC_API_KEY` | `anthropic/claude-3-sonnet`, `anthropic/claude-3-opus` |
| Google | `GOOGLE_API_KEY` | `google/gemini-pro` |

모델 식별자에 "/"가 포함되면 접두사를 프로바이더로, 나머지를 모델명으로 사용합니다. "/"가 없으면 기본 OpenAI 프로바이더로 라우팅됩니다.

## 기존 Agent (Deprecated)

기존 개별 에이전트는 `deprecated=True`로 마킹되었지만 동작은 유지됩니다. 점진적으로 Expert Agent로 전환할 수 있습니다.

| 에이전트 | 대체 Expert Agent |
|---------|------------------|
| sql_formatter | sql_expert (format) |
| sql_lint | sql_expert (lint) |
| query_explain | sql_expert (explain) |
| slow_query_analyzer | sql_expert (analyze_slow_query) |
| ddl_generator | schema_expert (generate_ddl) |
| schema_inspector | schema_expert (inspect_schema) |
| er_diagram | schema_expert (generate_er_diagram) |
| index_advisor | schema_expert (advise_index) |
| email_draft | communication (draft_email) |
| translation | communication (translate) |
| meeting_summary | communication (summarize_meeting) |
| document_review | document (review) |
| report_outline | document (outline_report) |
| presentation_helper | document (assist_presentation) |
| task_breakdown | planning (breakdown_task) |
| schedule_planner | planning (plan_schedule) |

## 프로젝트 구조

```
app/
├── main.py              # FastAPI 엔트리포인트
├── config.py            # 환경 변수 설정 (pydantic-settings)
├── health.py            # 헬스체크 라우터
├── logging_config.py    # 로깅 설정
├── static/index.html    # 웹 UI
├── agents/              # 라우터
│   ├── supervisor_router.py   # /supervisor/chat, /supervisor/chat/stream
│   ├── pipeline_router.py     # /supervisor/pipeline
│   ├── ops_router.py          # AI Ops 관리
│   └── sample_qa_agent.py     # 샘플 에이전트
├── framework/           # 에이전트 프레임워크 코어
│   ├── base.py          # 에이전트 베이스 클래스
│   ├── supervisor.py    # Supervisor 오케스트레이션 (LangGraph)
│   ├── registry.py      # Tool Agent 자동 발견/등록
│   ├── pipeline.py      # Pipeline_Executor (체이닝)
│   ├── state_store.py   # State_Store (PostgreSQL + InMemory)
│   ├── streaming.py     # SSE 스트리밍 유틸리티
│   ├── model_router.py  # Model_Router (멀티 모델)
│   ├── metrics.py       # 메트릭 수집기
│   ├── state.py         # 상태 관리
│   ├── nodes.py         # 그래프 노드
│   ├── model.py         # LLM 모델 추상화
│   ├── prompt.py        # 프롬프트 관리
│   └── manifest.py      # 매니페스트 로더
├── models/schemas.py    # Pydantic 스키마
├── services/            # 외부 서비스
│   ├── database.py      # PostgreSQL (asyncpg)
│   ├── elasticsearch.py # Elasticsearch
│   ├── llm.py           # OpenAI LLM + CostTracking
│   └── retry.py         # 재시도 로직
└── tool_agents/         # 플러그인 Tool Agents
    ├── _llm_utils.py           # call_llm 공용 유틸리티
    ├── sql_expert_agent/       # ⭐ SQL Expert (통합)
    ├── schema_expert_agent/    # ⭐ Schema Expert (통합)
    ├── communication_agent/    # ⭐ Communication (통합)
    ├── document_agent/         # ⭐ Document (통합)
    ├── planning_agent/         # ⭐ Planning (통합)
    ├── calculator_agent/       # 수식 계산
    ├── data_profiler_agent/    # 데이터 프로파일링
    ├── data_quality_agent/     # 데이터 품질 검사
    ├── echo_agent/             # 테스트용 에코
    ├── rag_search_agent/       # RAG 문서 검색
    ├── sql_formatter_agent/    # (deprecated → sql_expert)
    ├── sql_lint_agent/         # (deprecated → sql_expert)
    ├── query_explain_agent/    # (deprecated → sql_expert)
    └── ...                     # 기타 deprecated agents
```

## 새 Tool Agent 추가

```bash
python scripts/new_agent.py <agent_name>
```

생성되는 구조:
```
app/tool_agents/<agent_name>_agent/
├── __init__.py
├── factory.py    # 에이전트 팩토리
└── tool.py       # 도구 구현
```

## 테스트

```bash
# 의존성 설치
pip install -r requirements.txt
pip install pytest pytest-asyncio hypothesis httpx

# 전체 테스트
pytest tests/ -v

# 특정 테스트
pytest tests/test_integration.py -v       # 통합 테스트
pytest tests/test_pipeline.py -v          # 파이프라인
pytest tests/test_streaming.py -v         # SSE 스트리밍
pytest tests/test_state_store.py -v       # State Store
pytest tests/test_model_router_properties.py -v  # Model Router
pytest tests/test_sql_expert_agent.py -v  # SQL Expert
```

## 환경 변수

| 변수 | 필수 | 설명 | 예시 |
|------|------|------|------|
| OPENAI_API_KEY | ✅ | OpenAI API 키 | sk-... |
| DATABASE_URL | ✅ | PostgreSQL 연결 문자열 | postgresql+asyncpg://user:pw@host:5432/db |
| ELASTICSEARCH_URL | ✅ | Elasticsearch URL | http://localhost:9200 |
| ANTHROPIC_API_KEY | ❌ | Anthropic API 키 (멀티 모델) | sk-ant-... |
| GOOGLE_API_KEY | ❌ | Google AI API 키 (멀티 모델) | AIza... |
| SESSION_TTL_HOURS | ❌ | 세션 만료 시간 (기본: 24) | 48 |
| LOG_LEVEL | ❌ | 로그 레벨 (기본: INFO) | DEBUG, INFO, WARNING, ERROR |
| DEBUG_MODE | ❌ | 디버그 모드 (기본: false) | true/false |

## 기술 스택

- Python 3.13 / FastAPI / Uvicorn
- LangChain + LangGraph (멀티 에이전트 오케스트레이션)
- OpenAI / Anthropic / Google (멀티 모델)
- PostgreSQL (asyncpg) - 데이터 + 세션 상태 영속
- Elasticsearch 8.x
- Pydantic v2
- Docker Compose
- pytest + hypothesis (Property-Based Testing)

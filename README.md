# AI Agent Ops

데이터베이스 운영을 위한 AI 에이전트 플랫폼. LLM 기반의 Tool Agent들을 조합하여 DB 관련 작업을 자동화합니다.

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

## UI 화면

브라우저에서 `http://localhost:8000` 접속 시 채팅 UI가 표시됩니다.

- 왼쪽 사이드바에서 활성화할 Tool Agent를 클릭(복수 선택 가능)
- 하단 입력창에 질문 입력 → Supervisor Agent가 선택된 도구를 활용해 답변

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/` | 웹 UI |
| GET | `/health` | 헬스체크 |
| GET | `/docs` | Swagger UI (자동 생성) |
| POST | `/agent/chat` | 기본 Agent 대화 |
| POST | `/agent/supervisor/chat` | Supervisor Agent 대화 (Tool Agent 활성화) |
| GET | `/agent/supervisor/agents` | 등록된 Tool Agent 목록 |

## 프로젝트 구조

```
app/
├── main.py              # FastAPI 엔트리포인트
├── config.py            # 환경 변수 설정 (pydantic-settings)
├── health.py            # 헬스체크 라우터
├── logging_config.py    # 로깅 설정
├── static/index.html    # 웹 UI
├── agents/              # 라우터
│   ├── supervisor_router.py
│   ├── ops_router.py
│   └── sample_qa_agent.py
├── framework/           # 에이전트 프레임워크 코어
│   ├── base.py          # 에이전트 베이스 클래스
│   ├── supervisor.py    # Supervisor 오케스트레이션
│   ├── registry.py      # Tool Agent 자동 발견/등록
│   ├── state.py         # 상태 관리
│   ├── nodes.py         # 그래프 노드
│   ├── model.py         # LLM 모델 추상화
│   ├── prompt.py        # 프롬프트 관리
│   └── manifest.py      # 매니페스트 로더
├── models/schemas.py    # Pydantic 스키마
├── services/            # 외부 서비스
│   ├── database.py      # PostgreSQL (asyncpg)
│   ├── elasticsearch.py # Elasticsearch
│   ├── llm.py           # OpenAI LLM
│   └── retry.py         # 재시도 로직
└── tool_agents/         # 플러그인 Tool Agents
    ├── calculator_agent/
    ├── data_profiler_agent/
    ├── data_quality_agent/
    ├── ddl_generator_agent/
    ├── echo_agent/
    ├── er_diagram_agent/
    ├── index_advisor_agent/
    ├── query_explain_agent/
    ├── rag_search_agent/
    ├── schema_inspector_agent/
    ├── slow_query_analyzer_agent/
    ├── sql_formatter_agent/
    └── sql_lint_agent/
```

## Tool Agents

| 에이전트 | 설명 |
|---------|------|
| calculator | 수식 계산 |
| data_profiler | 테이블 데이터 프로파일링 |
| data_quality | 데이터 품질 검사 |
| ddl_generator | DDL 자동 생성 |
| echo | 테스트용 에코 |
| er_diagram | ER 다이어그램 생성 |
| index_advisor | 인덱스 추천 |
| query_explain | 쿼리 실행계획 분석 |
| rag_search | RAG 기반 문서 검색 |
| schema_inspector | DB 스키마 조회 |
| slow_query_analyzer | 슬로우 쿼리 분석 |
| sql_formatter | SQL 포맷팅 |
| sql_lint | SQL 린트 검사 |

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
pip install pytest pytest-asyncio hypothesis

# 전체 테스트
pytest tests/ -v

# 특정 테스트
pytest tests/test_health.py -v
pytest tests/test_tool_agents.py -v
pytest tests/test_supervisor.py -v
```

## 환경 변수

| 변수 | 필수 | 설명 | 예시 |
|------|------|------|------|
| OPENAI_API_KEY | ✅ | OpenAI API 키 | sk-... |
| DATABASE_URL | ✅ | PostgreSQL 연결 문자열 | postgresql+asyncpg://user:pw@host:5432/db |
| ELASTICSEARCH_URL | ✅ | Elasticsearch URL | http://localhost:9200 |
| LOG_LEVEL | ❌ | 로그 레벨 (기본: INFO) | DEBUG, INFO, WARNING, ERROR |
| DEBUG_MODE | ❌ | 디버그 모드 (기본: false) | true/false |

## 기술 스택

- Python 3.13 / FastAPI / Uvicorn
- LangChain + OpenAI
- PostgreSQL (asyncpg)
- Elasticsearch 8.x
- Pydantic v2
- Docker Compose

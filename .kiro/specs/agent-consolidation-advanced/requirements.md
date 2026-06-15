# Requirements Document

## Introduction

기존 LangGraph 기반 멀티 에이전트 오케스트레이션 시스템의 24개 Tool Agent 중 기능이 중복되는 에이전트들을 통합하고, 고급 기능(에이전트 체이닝, 영속 상태 관리, 스트리밍 응답, 멀티 모델 지원)을 추가하여 시스템의 효율성과 확장성을 높이는 개선 작업이다.

### 스코프 경계 (건드리지 않는 것)

- 프론트엔드(frontend/) 코드는 이번 스코프에 포함하지 않는다
- data_profiler, data_quality, data_insight, rag_search, regulation_check, calculator, echo 에이전트는 통합 대상이 아니며 기존 그대로 유지한다
- app/framework/base.py의 BaseAgentTool, BaseToolFactory 인터페이스는 변경하지 않고 확장만 한다
- 기존 개별 에이전트 디렉토리는 삭제하지 않고, deprecated 마킹하여 가역성을 보장한다
- FastAPI 기본 구조(main.py, health.py)는 변경하지 않고 라우터 추가만 한다

### 가역성 전략

- 통합 Expert Agent는 기존 에이전트 디렉토리와 병행 배치한다 (신규 디렉토리 생성)
- 기존 에이전트의 factory.py에 deprecated 플래그를 추가하되 동작은 유지한다
- Agent_Registry에서 deprecated 에이전트와 신규 Expert Agent를 모두 등록하여 점진적 전환을 지원한다

## Glossary

- **Orchestrator**: LangGraph StateGraph 기반 Supervisor Agent로, 사용자 질의를 분석하여 적절한 Tool Agent를 선택/호출하는 오케스트레이션 계층
- **Tool_Agent**: BaseAgentTool을 상속하여 특정 도메인 작업을 수행하는 플러그인 단위 에이전트
- **Expert_Agent**: 기존 유사 기능 Tool Agent들을 하나로 통합한 도메인 전문 에이전트로, 내부 서브커맨드 라우팅을 통해 여러 기능을 단일 진입점으로 제공
- **Agent_Registry**: app/framework/registry.py의 ToolAgentRegistry로 Tool Agent 팩토리를 자동 발견/등록하는 레지스트리
- **Pipeline**: 여러 Agent를 순차적으로 연결하여 이전 Agent의 출력(artifact)을 다음 Agent의 입력으로 전달하는 실행 구조
- **Pipeline_Executor**: Pipeline 정의를 받아 순차 실행, 입력 검증, 에러 처리, 중간 결과 수집을 수행하는 실행기
- **Pipeline_Definition**: 파이프라인 실행을 위한 JSON 직렬화 가능한 정의 객체로, steps 배열(agent_type, sub_command, input_mapping)을 포함
- **State_Store**: 대화 상태와 세션 이력을 영속적으로 저장하는 저장소 인터페이스 (PostgreSQL 또는 Redis 구현)
- **LLM_Provider**: 특정 LLM 서비스(OpenAI, Anthropic, Google 등)에 대한 추상화된 비동기 호출 인터페이스
- **Model_Router**: 요청의 모델 식별자를 파싱하여 적절한 LLM_Provider를 선택하고 호출을 위임하는 라우팅 계층
- **SSE_Stream**: Server-Sent Events 프로토콜을 통해 LLM 토큰 생성 결과를 실시간으로 클라이언트에 전달하는 스트림
- **call_llm**: Tool Agent가 LLM을 호출할 때 사용하는 공용 async 유틸리티 함수 (_llm_utils.py에 정의)
- **Execution_Trace**: Pipeline 또는 Agent 실행의 전체 이력을 기록하는 추적 객체로, 각 단계별 입력/출력/소요시간/상태를 포함
- **Sub_Command**: Expert_Agent 내부에서 특정 기능을 식별하는 문자열 키 (예: "format", "lint", "explain")

## Requirements

### Requirement 1: SQL Expert Agent 통합

**User Story:** As a 개발자, I want sql_formatter, sql_lint, query_explain, slow_query_analyzer 에이전트를 하나의 SQL Expert Agent로 통합하여, 단일 진입점으로 모든 SQL 관련 작업을 수행할 수 있게 하고 싶다.

#### Acceptance Criteria

1. THE Expert_Agent SHALL expose a unified "sql_expert" agent_type in the Agent_Registry with Sub_Commands: format, lint, explain, analyze_slow_query
2. WHEN a request with Sub_Command "format" is received, THE Expert_Agent SHALL apply keyword uppercasing and clause line-breaking to the input SQL and return a formatted SQL text artifact containing the formatted_sql and original fields
3. WHEN a request with Sub_Command "lint" is received, THE Expert_Agent SHALL analyze SQL for style violations and return a list of issues where each issue contains rule, severity (one of "error" or "warning"), message, and suggestion fields
4. WHEN a request with Sub_Command "explain" is received, THE Expert_Agent SHALL execute EXPLAIN (FORMAT JSON) against the database and return an execution plan analysis artifact containing total_cost, estimated_rows, node_count, nodes list, seq_scan_count, and warnings
5. WHEN a request with Sub_Command "explain" is received with analyze=true and the query does not start with SELECT, THE Expert_Agent SHALL return an error artifact indicating that ANALYZE is restricted to SELECT queries only
6. WHEN a request with Sub_Command "analyze_slow_query" is received, THE Expert_Agent SHALL query pg_stat_statements for the top N slowest queries (where N is the limit parameter, default 10, range 1–100) ordered by mean_exec_time descending and return the results in a queries array
7. THE Expert_Agent SHALL validate the sub_command parameter against the allowed list (format, lint, explain, analyze_slow_query) before execution
8. IF an unknown Sub_Command is requested, THEN THE Expert_Agent SHALL return an error artifact containing the requested sub_command value and the list of valid sub_commands
9. IF the sql or query input field is empty or missing for Sub_Commands that require it (format, lint, explain), THEN THE Expert_Agent SHALL return an error artifact indicating the missing required input field name
10. IF the database connection is unavailable when executing Sub_Commands "explain" or "analyze_slow_query", THEN THE Expert_Agent SHALL return an error artifact with type "sql_expert" and note "database_unavailable"
11. THE Expert_Agent SHALL accept the same input field names (sql for format and lint, query and analyze for explain, limit for analyze_slow_query) as the original individual agents for backward compatibility
12. THE Expert_Agent factory SHALL set deprecated=False while the original individual agent factories (sql_formatter_agent, sql_lint_agent, query_explain_agent, slow_query_analyzer_agent) SHALL each add a deprecated=True class attribute

### Requirement 2: Schema Expert Agent 통합

**User Story:** As a 개발자, I want ddl_generator, schema_inspector, er_diagram, index_advisor 에이전트를 하나의 Schema Expert Agent로 통합하여, DB 스키마 관련 작업을 효율적으로 처리할 수 있게 하고 싶다.

#### Acceptance Criteria

1. THE Expert_Agent SHALL expose a unified "schema_expert" agent_type in the Agent_Registry with Sub_Commands: generate_ddl, inspect_schema, generate_er_diagram, advise_index
2. WHEN a Sub_Command "generate_ddl" request is received with table_name (str) and columns (list of ColumnSpec with name, type, nullable, primary_key, unique, default fields), THE Expert_Agent SHALL produce valid PostgreSQL CREATE TABLE DDL including PRIMARY KEY constraints and CREATE INDEX statements for UNIQUE columns
3. WHEN a Sub_Command "inspect_schema" request is received with table (str) and optional schema_name (str, default "public"), THE Expert_Agent SHALL query the database information_schema and return an artifact with fields: table, schema, exists (bool), columns (list), indexes (list), constraints (list)
4. WHEN a Sub_Command "generate_er_diagram" request is received with optional schema_name (str, default "public"), THE Expert_Agent SHALL query table/column/FK data and produce an artifact containing a Mermaid erDiagram format string, table_count, and fk_count
5. WHEN a Sub_Command "advise_index" request is received with a query (str containing a SELECT statement), THE Expert_Agent SHALL extract predicate columns from WHERE/JOIN/ORDER BY clauses and return an artifact with recommendations (list of {columns, rationale, ddl}) and seq_scan_detected (bool or null)
6. THE Expert_Agent SHALL instantiate a single shared DBProvider instance and reuse it across all sub-function invocations within one request
7. IF the database connection is unavailable, THEN THE Expert_Agent SHALL return a standard error artifact with type "schema_expert" and note "database_unavailable" for Sub_Commands inspect_schema, generate_er_diagram, and advise_index (database-dependent commands)
8. THE Expert_Agent SHALL validate input schemas per sub_command and return a descriptive error artifact containing the sub_command name, the list of missing required fields, and the list of accepted fields for that sub_command
9. IF an unknown Sub_Command is requested, THEN THE Expert_Agent SHALL return an error artifact containing the requested sub_command value and the list of valid sub_commands (generate_ddl, inspect_schema, generate_er_diagram, advise_index)
10. THE Expert_Agent factory SHALL set deprecated=False while the original individual agent factories (ddl_generator, schema_inspector, er_diagram, index_advisor) SHALL add a deprecated=True class attribute
11. THE Expert_Agent SHALL accept the same input field names (table_name, columns, schema_name, table, query) as the original individual agents for backward compatibility

### Requirement 3: Communication Agent 통합

**User Story:** As a 개발자, I want email_draft, translation, meeting_summary 에이전트를 하나의 Communication Agent로 통합하여, 커뮤니케이션 관련 LLM 호출 패턴을 일원화하고 싶다.

#### Acceptance Criteria

1. THE Expert_Agent SHALL expose a unified "communication" agent_type in the Agent_Registry with Sub_Commands: draft_email, translate, summarize_meeting
2. WHEN a Sub_Command "draft_email" request is received with required fields purpose (str), recipient (str), key_points (str), and optional fields tone (str, default "formal") and language (str, default "ko"), THE Expert_Agent SHALL invoke call_llm with an email-specific system prompt and return a JSON artifact with subject (str) and body (str) fields
3. WHEN a Sub_Command "translate" request is received with required fields text (str) and target_lang (str), and optional field domain (str, default "general"), THE Expert_Agent SHALL invoke call_llm with a translation-specific system prompt and return a JSON artifact with source_text, translated_text, source_lang, and target_lang fields
4. WHEN a Sub_Command "summarize_meeting" request is received with required field content (str) and optional field meeting_title (str, default ""), THE Expert_Agent SHALL invoke call_llm with a meeting summary system prompt and return a structured artifact with title, attendees (list), agenda (list), decisions (list), and action_items (list of {assignee, task, deadline})
5. THE Expert_Agent SHALL use a shared internal method for LLM invocation that applies parse_json_response to all LLM outputs consistently
6. IF the call_llm invocation fails, THEN THE Expert_Agent SHALL retry exactly once with the same parameters and, on the second failure, return an error artifact with type "communication", the sub_command name, and the failure reason from the exception message
7. IF the LLM response cannot be parsed as valid JSON, THEN THE Expert_Agent SHALL use the raw response text as the primary content field in the artifact while preserving the artifact type as "communication"
8. IF a required input field for the requested sub_command is missing or empty, THEN THE Expert_Agent SHALL return an error artifact listing the missing field names without invoking call_llm
9. IF an unknown Sub_Command is requested, THEN THE Expert_Agent SHALL return an error artifact containing the requested sub_command value and the list of valid sub_commands (draft_email, translate, summarize_meeting)
10. THE Expert_Agent factory SHALL set deprecated=False while the original individual agent factories (email_draft, translation, meeting_summary) SHALL add a deprecated=True class attribute

### Requirement 4: Document Agent 통합

**User Story:** As a 개발자, I want document_review, report_outline, presentation_helper 에이전트를 하나의 Document Agent로 통합하여, 문서 관련 작업을 통합 처리하고 싶다.

#### Acceptance Criteria

1. THE Expert_Agent SHALL expose a unified "document" agent_type in the Agent_Registry with Sub_Commands: review, outline_report, assist_presentation
2. WHEN a Sub_Command "review" request is received with required field document (str) and optional field doc_type (str, default "general"), THE Expert_Agent SHALL analyze the document via call_llm and return an artifact with issues (list of {category, location, description}), suggestions (list of {original, revised, reason}), overall_score (int 1-10), and doc_type (str)
3. WHEN a Sub_Command "outline_report" request is received with required fields topic (str) and purpose (str), and optional field audience (str, default "general"), THE Expert_Agent SHALL invoke call_llm and return an artifact with topic, purpose, and outline_sections (list of {title, key_points, subsections})
4. WHEN a Sub_Command "assist_presentation" request is received with required fields topic (str) and audience (str), and optional field duration_minutes (int, default 15), THE Expert_Agent SHALL invoke call_llm and return an artifact with topic, audience, duration_minutes, and slides (list of {slide_number, title, key_points, script})
5. THE Expert_Agent SHALL validate that required input fields exist and are non-empty strings for each Sub_Command before invoking call_llm, and return an error artifact listing missing fields if validation fails
6. IF the call_llm invocation fails, THEN THE Expert_Agent SHALL return an error artifact with type "document", the sub_command name, and the failure reason from the exception message
7. IF the LLM response cannot be parsed as valid JSON, THEN THE Expert_Agent SHALL use the raw response text as the primary content field in the artifact while preserving the artifact type as "document"
8. IF an unknown Sub_Command is requested, THEN THE Expert_Agent SHALL return an error artifact containing the requested sub_command value and the list of valid sub_commands (review, outline_report, assist_presentation)

### Requirement 5: Planning Agent 통합

**User Story:** As a 개발자, I want task_breakdown, schedule_planner 에이전트를 하나의 Planning Agent로 통합하여, 계획 관련 작업을 단일 에이전트에서 처리하고 싶다.

#### Acceptance Criteria

1. THE Expert_Agent SHALL expose a unified "planning" agent_type in the Agent_Registry with Sub_Commands: breakdown_task, plan_schedule
2. WHEN a Sub_Command "breakdown_task" request is received with required fields project (str) and goal (str), and optional field constraints (str, default ""), THE Expert_Agent SHALL invoke call_llm and return an artifact with project_name (str), tasks (list of {task_name, description, estimated_hours, priority, dependencies}), dependencies (list of [predecessor, successor] pairs), and total_estimated_hours (number)
3. WHEN a Sub_Command "plan_schedule" request is received with required field tasks (str containing task list text) and optional field start_date (str, default ""), THE Expert_Agent SHALL invoke call_llm and return an artifact with tasks (list of {name, estimated_hours, deadline, priority}), schedule (list of {date, tasks}), and priorities (list of str)
4. THE Expert_Agent SHALL validate that required input fields (project and goal for breakdown_task; tasks for plan_schedule) are non-empty strings before invoking call_llm, and return an error artifact listing missing fields if validation fails
5. IF the call_llm invocation fails, THEN THE Expert_Agent SHALL return an error artifact with type "planning", the sub_command name, and the failure reason from the exception message
6. IF the LLM response cannot be parsed as valid JSON, THEN THE Expert_Agent SHALL use the raw response text as the primary content field in the artifact while preserving the artifact type as "planning"
7. IF an unknown Sub_Command is requested, THEN THE Expert_Agent SHALL return an error artifact containing the requested sub_command value and the list of valid sub_commands (breakdown_task, plan_schedule)

### Requirement 6: call_llm 유틸리티 구현

**User Story:** As a 개발자, I want _llm_utils.py의 call_llm 함수가 완전히 구현되어, 모든 LLM 의존 Tool Agent들이 안정적으로 LLM을 호출할 수 있게 하고 싶다.

#### Acceptance Criteria

1. THE call_llm function SHALL accept required parameters system_prompt (str) and user_input (str) and return the LLM response content as a string
2. THE call_llm function SHALL accept optional parameters: model (str, default "gpt-4o-mini"), temperature (float, default 0.0), max_tokens (int, default 4096)
3. THE call_llm function SHALL use the Model_Router to resolve the LLM_Provider from the model parameter and invoke it
4. THE call_llm function SHALL attach a CostTrackingCallback instance for token usage and cost logging on every invocation
5. IF the model parameter is empty or None, THEN THE call_llm function SHALL use the default model "gpt-4o-mini"
6. IF the LLM_Provider raises an exception, THEN THE call_llm function SHALL re-raise a RuntimeError with message containing the model name, provider name, and original error message
7. THE call_llm function SHALL be defined as an async function (async def) to be compatible with the existing async Tool Agent _arun execution pattern
8. THE call_llm function SHALL validate that system_prompt and user_input are non-empty strings and raise ValueError if either is empty or contains only whitespace characters
9. IF the temperature parameter is outside the range 0.0 to 2.0 (inclusive), THEN THE call_llm function SHALL raise ValueError indicating the valid range
10. IF the max_tokens parameter is less than 1 or greater than 128000, THEN THE call_llm function SHALL raise ValueError indicating the valid range
11. THE call_llm function SHALL complete the LLM invocation or raise an exception within 120 seconds; IF the invocation exceeds 120 seconds, THEN the function SHALL raise a TimeoutError with the model name and elapsed time

### Requirement 7: Agent Pipeline (체이닝) 기능

**User Story:** As a 개발자, I want 여러 Agent를 파이프라인으로 연결하여 복합 작업을 순차 자동 실행할 수 있게 하고 싶다.

#### Acceptance Criteria

1. THE Pipeline_Executor SHALL accept a Pipeline_Definition containing a "steps" array where each step specifies agent_type (str), sub_command (str, optional), and input_mapping (dict mapping target field names to source expressions)
2. WHEN a pipeline is executed, THE Pipeline_Executor SHALL invoke each step sequentially, resolving input_mapping expressions from the previous step's artifact to construct the current step's input
3. THE Pipeline_Executor SHALL maintain an Execution_Trace recording each step's agent_type, sub_command, input, output artifact, duration_ms (integer milliseconds), and status (success/failed)
4. IF any step in the pipeline fails (returns error artifact or raises exception), THEN THE Pipeline_Executor SHALL halt execution immediately and return the Execution_Trace with all completed steps plus the failed step, setting the overall trace status to "failed"
5. WHEN pipeline execution begins, THE Pipeline_Executor SHALL validate that all agent_types in the steps exist in the Agent_Registry and return a validation error with the list of missing agent_types before execution starts
6. WHEN pipeline execution completes successfully, THE Pipeline_Executor SHALL record total_duration_ms and step_count in the MetricsCollector under the metric key "pipeline_execution"
7. THE Orchestrator SHALL expose a POST /supervisor/pipeline endpoint that accepts a Pipeline_Definition JSON body and returns the Execution_Trace as a JSON response with HTTP 200 for completed/failed pipelines and HTTP 422 for validation errors
8. THE Pipeline_Executor SHALL enforce a maximum of 10 steps per pipeline and return a validation error indicating the maximum allowed step count if exceeded
9. IF a step's input_mapping references a field that does not exist in the previous step's artifact, THEN THE Pipeline_Executor SHALL halt and return an error with the missing field name and step index
10. THE Pipeline_Definition SHALL require at least 1 step; IF the steps array is empty, THEN THE Pipeline_Executor SHALL return a validation error indicating that at least one step is required
11. WHEN the first step of a pipeline is executed, THE Pipeline_Executor SHALL use the pipeline request's initial input data as the source for input_mapping resolution; IF no initial input is provided and the first step has input_mapping references, THEN THE Pipeline_Executor SHALL return an error indicating the missing initial input

### Requirement 8: 영속 상태 관리 (Persistent State)

**User Story:** As a 개발자, I want 대화 상태와 세션 이력을 PostgreSQL에 영속 저장하여, 서버 재시작 후에도 대화를 이어갈 수 있게 하고 싶다.

#### Acceptance Criteria

1. THE State_Store interface SHALL define async methods: save_state(session_id, state), load_state(session_id), delete_state(session_id), list_sessions(limit, offset)
2. THE State_Store PostgreSQL implementation SHALL store session state in a table with columns: session_id (VARCHAR(64), PK), state_json (JSONB), created_at (TIMESTAMPTZ), updated_at (TIMESTAMPTZ), expires_at (TIMESTAMPTZ)
3. WHEN a conversation message is processed via /supervisor/chat, THE Orchestrator SHALL call save_state with the updated SupervisorState after the graph invocation completes
4. WHEN a request includes a session_id, THE Orchestrator SHALL call load_state to retrieve existing state and resume the conversation from the persisted state
5. IF load_state returns None for a given session_id, THEN THE Orchestrator SHALL start a new conversation with a new state entry and return the new session_id in the response
6. IF the State_Store is unavailable (connection error or timeout within 5 seconds), THEN THE Orchestrator SHALL fall back to InMemorySaver, log a warning with the connection error details, and include a "state_persistence": "in_memory" field in the response
7. THE State_Store SHALL set expires_at to current_time + configured TTL (default 24 hours, configurable via SESSION_TTL_HOURS environment variable) on every save_state call, and a periodic cleanup process SHALL delete expired sessions
8. THE State_Store SHALL serialize SupervisorState messages using LangChain's message serialization (messages_to_dict / messages_from_dict) for cross-process portability
9. THE list_sessions method SHALL accept limit (integer, 1 to 100, default 50) and offset (integer, 0 or greater, default 0) parameters and return sessions ordered by updated_at descending
10. IF save_state is called with a session_id that already exists, THEN THE State_Store SHALL update the existing record's state_json, updated_at, and expires_at fields without creating a duplicate entry (UPSERT)
11. THE session_id SHALL be a non-empty string with maximum length of 64 characters containing only alphanumeric characters, hyphens, and underscores; IF an invalid session_id is provided, THEN THE State_Store SHALL raise ValueError

### Requirement 9: 스트리밍 응답 (SSE)

**User Story:** As a 개발자, I want LLM 응답을 토큰 단위로 실시간 스트리밍하여, 사용자가 응답 완료를 기다리지 않고 결과를 확인할 수 있게 하고 싶다.

#### Acceptance Criteria

1. THE Orchestrator SHALL expose a POST /supervisor/chat/stream endpoint that accepts the same request body as /supervisor/chat and returns a text/event-stream response with Content-Type "text/event-stream" and Cache-Control "no-cache" headers
2. WHEN a streaming request is received, THE Orchestrator SHALL invoke the Supervisor graph with astream_events and emit SSE events for each token generated by the LLM
3. THE SSE_Stream SHALL emit events with the format: "event: {event_type}\ndata: {json_payload}\n\n" where event_type is one of: token, tool_call, tool_result, done, error
4. WHEN a token event is emitted, THE SSE_Stream data payload SHALL contain fields: content (str, the token text) and timestamp (ISO 8601 format)
5. WHEN a Tool Agent is invoked during streaming, THE SSE_Stream SHALL emit a "tool_call" event with agent_type and sub_command fields, followed by a "tool_result" event with the artifact after the tool execution completes
6. WHEN the LLM completes generation, THE SSE_Stream SHALL emit a "done" event with fields: full_response (str), session_id (str), tool_calls (list of agent names invoked during this request), and close the connection
7. IF an error occurs during streaming, THEN THE SSE_Stream SHALL emit an "error" event with fields: error_message (str, description without internal stack traces), error_type (str, classification such as "llm_error", "tool_error", "timeout"), and close the connection
8. IF the client disconnects before the stream completes, THEN THE SSE_Stream SHALL detect the disconnection within 5 seconds and terminate the LLM generation to release resources
9. IF no token event is emitted within 60 seconds during an active stream, THEN THE SSE_Stream SHALL emit an "error" event with error_type "timeout" and close the connection
10. THE SSE_Stream SHALL emit a heartbeat comment line (": heartbeat\n\n") every 15 seconds during periods of no token generation to prevent proxy/load-balancer timeout disconnections

### Requirement 10: 멀티 모델 지원

**User Story:** As a 개발자, I want OpenAI 외에 Anthropic Claude, Google Gemini, 로컬 모델 등 다양한 LLM을 선택적으로 사용할 수 있게 하고 싶다.

#### Acceptance Criteria

1. THE Model_Router SHALL maintain a provider_registry dict mapping provider name strings ("openai", "anthropic", "google", "local") to LLM_Provider instances
2. THE LLM_Provider interface SHALL define an async method: ainvoke(messages: list, model: str, temperature: float, max_tokens: int) -> str that returns the response content text
3. WHEN a model identifier with provider prefix (e.g., "anthropic/claude-3-sonnet") is received, THE Model_Router SHALL split on the first "/" character, use the prefix as provider key, and the remainder as the model name
4. IF no "/" separator exists in the model identifier, THEN THE Model_Router SHALL route to the "openai" provider with the full string as the model name
5. THE Model_Router SHALL pass the CostTrackingCallback to all providers that support callback attachment for unified cost logging
6. WHEN a new LLM_Provider is added to the provider_registry via a register_provider(name, provider) method, THE Model_Router SHALL make it available for routing without requiring changes to existing agents
7. IF a specified provider name is not found in the provider_registry, THEN THE Model_Router SHALL raise a ValueError with message containing the requested provider name and the list of registered provider names
8. IF the required API key environment variable for a provider is not configured, THEN THE Model_Router SHALL raise a ConfigurationError at provider registration time with the missing variable name and provider name
9. THE OpenAI LLM_Provider SHALL be the default implementation, using langchain_openai.ChatOpenAI with the existing OPENAI_API_KEY from Settings
10. THE Model_Router SHALL treat provider name lookup as case-insensitive; "OpenAI", "OPENAI", and "openai" SHALL all resolve to the same provider
11. IF the LLM_Provider's ainvoke method raises a provider-specific exception (e.g., rate limit, authentication failure), THEN THE Model_Router SHALL wrap it in a standardized RuntimeError with fields: provider name, model name, original error type, and original error message
12. THE register_provider method SHALL reject duplicate provider names and raise ValueError indicating the provider name is already registered; to replace a provider, the caller SHALL use an explicit replace_provider(name, provider) method

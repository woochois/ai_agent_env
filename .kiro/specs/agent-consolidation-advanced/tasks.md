# Implementation Plan: Agent Consolidation Advanced

## Overview

이 구현 계획은 기존 24개 Tool Agent 중 유사 기능 에이전트를 5개 Expert Agent로 통합하고, call_llm 유틸리티 완성, Agent Pipeline, 영속 상태 관리, SSE 스트리밍, 멀티 모델 지원 기능을 추가하는 작업을 단계적으로 수행한다. Model_Router와 call_llm 인프라를 먼저 구축한 후, Expert Agent 통합을 병렬로 진행하고, 고급 기능(Pipeline, State_Store, SSE)을 순차 구현한다.

## Tasks

- [x] 1. Model_Router 및 LLM_Provider 인프라 구축
  - 모든 Expert Agent와 call_llm이 Model_Router에 의존하므로 최우선 구현
  - [x] 1.1 Create `app/framework/model_router.py` with `LLMProvider` abstract base class defining `async ainvoke(messages, model, temperature, max_tokens) -> str`
    - _Requirements: 10.1, 10.2_
  - [ ] 1.2 Implement `ModelRouter` class with `register_provider(name, provider)`, `resolve(model_identifier) -> tuple[LLMProvider, str]`, and `async ainvoke(model_identifier, messages, **kwargs) -> str`
    - _Requirements: 10.1, 10.3, 10.4, 10.6_
  - [ ] 1.3 Implement `OpenAIProvider(LLMProvider)` using `langchain_openai.ChatOpenAI` with `CostTrackingCallback` attachment
    - _Requirements: 10.5, 10.9_
  - [ ] 1.4 Implement `AnthropicProvider(LLMProvider)` using `langchain_anthropic.ChatAnthropic` (optional import with graceful fallback)
    - _Requirements: 10.1_
  - [ ] 1.5 Implement `GoogleProvider(LLMProvider)` using `langchain_google_genai.ChatGoogleGenerativeAI` (optional import with graceful fallback)
    - _Requirements: 10.1_
  - [ ] 1.6 Add provider prefix parsing in `resolve()`: split on first "/" for provider/model, default to "openai" when no "/" present
    - _Requirements: 10.3, 10.4, 10.10_
  - [ ] 1.7 Add `ConfigurationError` exception for missing API keys with provider name and variable name in message
    - _Requirements: 10.8_
  - [ ] 1.8 Create singleton `get_model_router()` function that initializes providers based on available environment variables
    - _Requirements: 10.6, 10.9_
  - [ ] 1.9 Update `app/framework/model.py` `create_chat_model()` to internally use `ModelRouter` while maintaining existing function signature
    - _Requirements: 10.6_
  - [ ]* 1.10 Add unit tests for ModelRouter: prefix parsing, provider registration, missing provider error, missing API key error
    - **Property 10: Model_Router 라우팅 결정론성**
    - **Property 11: Model_Router 프로바이더 레지스트리 관리**
    - **Validates: Requirements 10.3, 10.4, 10.6, 10.7, 10.8, 10.10, 10.11, 10.12**

- [x] 2. call_llm 유틸리티 완성
  - Expert Agent들이 call_llm에 의존
  - [ ] 2.1 Implement `call_llm` async function in `app/tool_agents/_llm_utils.py` with parameters: system_prompt (str), user_input (str), model (str="gpt-4o-mini"), temperature (float=0.0), max_tokens (int=4096)
    - _Requirements: 6.1, 6.2, 6.7_
  - [ ] 2.2 Add input validation: raise `ValueError` if system_prompt or user_input is empty string or None
    - _Requirements: 6.8_
  - [ ] 2.3 Construct message list with `SystemMessage(content=system_prompt)` and `HumanMessage(content=user_input)` and call `get_model_router().ainvoke()`
    - _Requirements: 6.3_
  - [ ] 2.4 Add error handling: catch provider exceptions and re-raise as `RuntimeError` with model name, provider name, and original error message
    - _Requirements: 6.6_
  - [ ] 2.5 Handle default model: if model parameter is None or empty, use "gpt-4o-mini"
    - _Requirements: 6.5_
  - [ ]* 2.6 Add unit tests for call_llm: successful invocation (mocked), empty input validation, error propagation
    - **Property 9: call_llm 파라미터 검증**
    - **Validates: Requirements 6.1, 6.6, 6.8, 6.9, 6.10**

- [x] 3. SQL Expert Agent 통합
  - [ ] 3.1 Create directory `app/tool_agents/sql_expert_agent/` with `__init__.py`
    - _Requirements: 1.1_
  - [ ] 3.2 Create `tool.py` with `SqlExpertInput` schema (sub_command, sql, query, analyze fields) and `SqlExpertTool` class
    - _Requirements: 1.1, 1.7, 1.11_
  - [ ] 3.3 Implement `_handle_format` method reusing logic from `sql_formatter_agent/tool.py` `format_sql()` function
    - _Requirements: 1.2_
  - [ ] 3.4 Implement `_handle_lint` method reusing logic from `sql_lint_agent/tool.py`
    - _Requirements: 1.3_
  - [ ] 3.5 Implement `_handle_explain` method reusing logic from `query_explain_agent/tool.py` with shared DBProvider
    - _Requirements: 1.4, 1.5_
  - [ ] 3.6 Implement `_handle_analyze_slow_query` method reusing logic from `slow_query_analyzer_agent/tool.py`
    - _Requirements: 1.6_
  - [ ] 3.7 Add sub_command validation: return error artifact with valid commands list for unknown sub_commands
    - _Requirements: 1.7, 1.8, 1.9, 1.10_
  - [ ] 3.8 Create `factory.py` with `SqlExpertFactory` (agent_type="sql_expert", category="SQL", deprecated=False)
    - _Requirements: 1.12_
  - [ ] 3.9 Add `deprecated = True` class attribute to existing `SqlFormatterFactory`, `SqlLintFactory`, `QueryExplainFactory`, `SlowQueryAnalyzerFactory`
    - _Requirements: 1.12_
  - [ ]* 3.10 Add unit tests for sub_command routing and invalid sub_command error
    - **Property 1: Expert Agent Sub_Command 라우팅 및 입력 검증**
    - **Property 2: SQL Expert 서브커맨드 아티팩트 구조 정합성**
    - **Property 3: EXPLAIN ANALYZE는 SELECT 전용**
    - **Validates: Requirements 1.7, 1.8, 1.9, 1.2, 1.3, 1.5**

- [x] 4. Schema Expert Agent 통합
  - [ ] 4.1 Create directory `app/tool_agents/schema_expert_agent/` with `__init__.py`
    - _Requirements: 2.1_
  - [ ] 4.2 Create `tool.py` with `SchemaExpertInput` schema (sub_command, plus per-command fields) and `SchemaExpertTool` class
    - _Requirements: 2.1, 2.8, 2.11_
  - [ ] 4.3 Implement `_handle_generate_ddl` reusing logic from `ddl_generator_agent/tool.py`
    - _Requirements: 2.2_
  - [ ] 4.4 Implement `_handle_inspect_schema` reusing logic from `schema_inspector_agent/tool.py`
    - _Requirements: 2.3_
  - [ ] 4.5 Implement `_handle_generate_er_diagram` reusing logic from `er_diagram_agent/tool.py`
    - _Requirements: 2.4_
  - [ ] 4.6 Implement `_handle_advise_index` reusing logic from `index_advisor_agent/tool.py`
    - _Requirements: 2.5_
  - [ ] 4.7 Share single DBProvider instance across all handlers; return "database_unavailable" error artifact when connection fails
    - _Requirements: 2.6, 2.7_
  - [ ] 4.8 Create `factory.py` with `SchemaExpertFactory` (agent_type="schema_expert", category="Schema")
    - _Requirements: 2.10_
  - [ ] 4.9 Add `deprecated = True` to existing ddl_generator, schema_inspector, er_diagram, index_advisor factories
    - _Requirements: 2.10_
  - [ ]* 4.10 Add unit tests for sub_command routing and database unavailability handling
    - **Property 1: Expert Agent Sub_Command 라우팅 및 입력 검증**
    - **Property 4: Schema Expert DDL 생성 정합성**
    - **Property 5: Schema Expert Index Advisor 추출 정합성**
    - **Validates: Requirements 2.8, 2.9, 2.2, 2.5**

- [x] 5. Communication Agent 통합
  - [ ] 5.1 Create directory `app/tool_agents/communication_agent/` with `__init__.py`
    - _Requirements: 3.1_
  - [ ] 5.2 Create `tool.py` with `CommunicationInput` schema (sub_command + per-command fields) and `CommunicationTool` class
    - _Requirements: 3.1, 3.8, 3.9_
  - [ ] 5.3 Implement `_handle_draft_email` reusing email_draft_agent logic with call_llm
    - _Requirements: 3.2_
  - [ ] 5.4 Implement `_handle_translate` reusing translation_agent logic with call_llm
    - _Requirements: 3.3_
  - [ ] 5.5 Implement `_handle_summarize_meeting` reusing meeting_summary_agent logic with call_llm
    - _Requirements: 3.4_
  - [ ] 5.6 Add shared `_invoke_llm_with_retry` method: retry once on failure, return error artifact on second failure
    - _Requirements: 3.5, 3.6_
  - [ ] 5.7 Add JSON parse fallback: if parse_json_response returns None, use raw text as content
    - _Requirements: 3.7_
  - [ ] 5.8 Create `factory.py` with `CommunicationFactory` (agent_type="communication", category="Communication")
    - _Requirements: 3.10_
  - [ ] 5.9 Add `deprecated = True` to existing email_draft, translation, meeting_summary factories
    - _Requirements: 3.10_
  - [ ]* 5.10 Add unit tests for retry logic and JSON parse fallback
    - **Property 7: LLM 호출 실패 시 에러 아티팩트 및 재시도**
    - **Property 8: LLM JSON 파싱 실패 시 원본 텍스트 보존**
    - **Validates: Requirements 3.6, 3.7**

- [x] 6. Document Agent 통합
  - [ ] 6.1 Create directory `app/tool_agents/document_agent/` with `__init__.py`
    - _Requirements: 4.1_
  - [ ] 6.2 Create `tool.py` with `DocumentInput` schema and `DocumentTool` class
    - _Requirements: 4.1, 4.5, 4.8_
  - [ ] 6.3 Implement `_handle_review` returning issues list artifact (category, severity, description, suggestion)
    - _Requirements: 4.2_
  - [ ] 6.4 Implement `_handle_outline_report` returning sections array artifact (title, key_points, estimated_length)
    - _Requirements: 4.3_
  - [ ] 6.5 Implement `_handle_assist_presentation` returning slides array artifact (title, bullet_points, speaker_notes)
    - _Requirements: 4.4_
  - [ ] 6.6 Add input validation per sub_command (required fields check before LLM call)
    - _Requirements: 4.5_
  - [ ] 6.7 Create `factory.py` with `DocumentFactory` (agent_type="document", category="Documentation")
    - _Requirements: 4.1_
  - [ ] 6.8 Add `deprecated = True` to existing document_review, report_outline, presentation_helper factories
    - _Requirements: 4.1_
  - [ ]* 6.9 Add unit tests for input validation and sub_command routing
    - **Property 1: Expert Agent Sub_Command 라우팅 및 입력 검증**
    - **Property 6: LLM 기반 Expert Agent 아티팩트 구조**
    - **Validates: Requirements 4.5, 4.8, 4.2, 4.3, 4.4**

- [x] 7. Planning Agent 통합
  - [ ] 7.1 Create directory `app/tool_agents/planning_agent/` with `__init__.py`
    - _Requirements: 5.1_
  - [ ] 7.2 Create `tool.py` with `PlanningInput` schema and `PlanningTool` class
    - _Requirements: 5.1, 5.4, 5.7_
  - [ ] 7.3 Implement `_handle_breakdown_task` returning sub_tasks array artifact (title, description, estimated_hours, dependencies)
    - _Requirements: 5.2_
  - [ ] 7.4 Implement `_handle_plan_schedule` returning timeline array artifact (task_name, start_date, end_date, milestone_flag)
    - _Requirements: 5.3_
  - [ ] 7.5 Add validation: reject empty task descriptions with descriptive error
    - _Requirements: 5.4_
  - [ ] 7.6 Create `factory.py` with `PlanningFactory` (agent_type="planning", category="Planning")
    - _Requirements: 5.1_
  - [ ] 7.7 Add `deprecated = True` to existing task_breakdown, schedule_planner factories
    - _Requirements: 5.1_
  - [ ]* 7.8 Add unit tests for both sub_commands and empty input validation
    - **Property 1: Expert Agent Sub_Command 라우팅 및 입력 검증**
    - **Property 6: LLM 기반 Expert Agent 아티팩트 구조**
    - **Validates: Requirements 5.4, 5.7, 5.2, 5.3**

- [x] 8. Checkpoint - 핵심 기능 검증
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Agent Pipeline (체이닝) 구현
  - [ ] 9.1 Create `app/framework/pipeline.py` with Pydantic models: `PipelineStep`, `PipelineDefinition`, `StepResult`, `ExecutionTrace`
    - _Requirements: 7.1, 7.3_
  - [ ] 9.2 Implement `PipelineExecutor.__init__(registry: ToolAgentRegistry)` and validation method
    - _Requirements: 7.5_
  - [ ] 9.3 Implement `validate()`: check all agent_types exist in registry, step count <= 10
    - _Requirements: 7.5, 7.8, 7.10_
  - [ ] 9.4 Implement `execute()`: sequential step execution with artifact passing via input_mapping resolution
    - _Requirements: 7.2, 7.3_
  - [ ] 9.5 Implement input_mapping resolution: parse "$.field_name" expressions from previous step's artifact
    - _Requirements: 7.2, 7.9, 7.11_
  - [ ] 9.6 Add error handling: halt on failed step, return partial ExecutionTrace with failed step info
    - _Requirements: 7.4_
  - [ ] 9.7 Add input_mapping field existence validation: halt with error if referenced field not in previous artifact
    - _Requirements: 7.9_
  - [ ] 9.8 Record metrics: total_duration_ms and step_count via MetricsCollector on completion
    - _Requirements: 7.6_
  - [ ] 9.9 Create `app/agents/pipeline_router.py` with `POST /supervisor/pipeline` endpoint
    - _Requirements: 7.7_
  - [ ] 9.10 Register pipeline_router in `app/main.py`
    - _Requirements: 7.7_
  - [ ]* 9.11 Add unit tests: successful multi-step pipeline, step failure halt, validation errors, input_mapping resolution
    - **Property 12: Pipeline Execution Trace 완전성**
    - **Property 13: Pipeline input_mapping 해석**
    - **Property 14: Pipeline 사전 검증**
    - **Validates: Requirements 7.2, 7.3, 7.4, 7.5, 7.8, 7.9, 7.10, 7.11**

- [x] 10. 영속 상태 관리 구현
  - [ ] 10.1 Create `app/framework/state_store.py` with abstract `StateStore` class (save_state, load_state, delete_state, list_sessions)
    - _Requirements: 8.1_
  - [ ] 10.2 Implement `PostgresStateStore` with asyncpg/SQLAlchemy async: create sessions table if not exists on init
    - _Requirements: 8.2_
  - [ ] 10.3 Implement `save_state`: upsert session with state_json (JSONB), updated_at, expires_at = now + TTL
    - _Requirements: 8.3, 8.7, 8.10_
  - [ ] 10.4 Implement `load_state`: fetch by session_id, return None if not found or expired
    - _Requirements: 8.4, 8.5_
  - [ ] 10.5 Implement `delete_state` and `list_sessions` with limit/offset pagination
    - _Requirements: 8.9_
  - [ ] 10.6 Implement `get_checkpointer()` function: try PostgresSaver, fallback to InMemorySaver with warning log
    - _Requirements: 8.6_
  - [ ] 10.7 Add TTL configuration via Settings (STATE_TTL_HOURS, default=24)
    - _Requirements: 8.7_
  - [ ] 10.8 Update `supervisor_router.py` `supervisor_chat()`: use `get_checkpointer()` instead of inline InMemorySaver
    - _Requirements: 8.3, 8.4_
  - [ ] 10.9 Add session state persistence: save after graph invocation, load when session_id provided
    - _Requirements: 8.3, 8.4, 8.5_
  - [ ] 10.10 Add expired session cleanup: background task or on-read check
    - _Requirements: 8.7_
  - [ ]* 10.11 Add unit tests: save/load round-trip, expiration, fallback behavior
    - **Property 15: State_Store 영속성 라운드트립**
    - **Property 16: State_Store session_id 검증**
    - **Property 17: State_Store TTL 및 페이지네이션**
    - **Validates: Requirements 8.4, 8.7, 8.8, 8.9, 8.10, 8.11**

- [x] 11. SSE 스트리밍 응답 구현
  - [ ] 11.1 Create `app/framework/streaming.py` with `SSEEvent` model and `format_sse_event(event_type, data)` helper
    - _Requirements: 9.3_
  - [ ] 11.2 Implement `stream_supervisor_response()` async generator using LangGraph `astream_events`
    - _Requirements: 9.2_
  - [ ] 11.3 Map LangGraph events to SSE event types: on_chat_model_stream → "token", on_tool_start → "tool_call", on_tool_end → "tool_result"
    - _Requirements: 9.3, 9.4, 9.5_
  - [ ] 11.4 Emit "done" event on stream completion with full_response, session_id, tool_calls
    - _Requirements: 9.6_
  - [ ] 11.5 Emit "error" event on exception with error_message and error_type, then close
    - _Requirements: 9.7_
  - [ ] 11.6 Add `POST /supervisor/chat/stream` endpoint in `supervisor_router.py` returning `StreamingResponse(media_type="text/event-stream")`
    - _Requirements: 9.1_
  - [ ]* 11.7 Add unit tests: event format validation, error event on failure, done event as last event
    - **Property 18: SSE 이벤트 형식 및 순서**
    - **Validates: Requirements 9.3, 9.4, 9.6, 9.7**

- [x] 12. 통합 테스트 및 문서화
  - [ ] 12.1 Create integration test: pipeline with sql_expert format → explain chaining
    - _Requirements: 7.2, 7.3_
  - [ ] 12.2 Create integration test: streaming endpoint with mocked LLM
    - _Requirements: 9.1, 9.2_
  - [ ] 12.3 Create integration test: state persistence across multiple requests with same session_id
    - _Requirements: 8.3, 8.4_
  - [ ] 12.4 Create integration test: multi-model routing (mock providers)
    - _Requirements: 10.3, 10.4_
  - [ ] 12.5 Update README.md with new architecture diagram, new endpoints, and usage examples
    - _Requirements: all_
  - [ ] 12.6 Add API documentation for /supervisor/pipeline and /supervisor/chat/stream endpoints
    - _Requirements: 7.7, 9.1_
  - [ ] 12.7 Verify all deprecated agents still function correctly (backward compatibility smoke test)
    - _Requirements: 1.12, 2.10, 3.10_
  - [ ] 12.8 Run full test suite and fix any regressions
    - _Requirements: all_

- [x] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Model_Router (Task 1) and call_llm (Task 2) are foundational and must be completed before Expert Agent tasks (3-7)
- Expert Agent tasks (3-7) can be implemented in parallel once infrastructure is ready
- Pipeline (Task 9), State_Store (Task 10), and SSE (Task 11) depend on the framework infrastructure but are independent of each other

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6", "1.7", "1.8"] },
    { "id": 1, "tasks": ["1.9", "1.10", "2.1", "2.2", "2.3", "2.4", "2.5"] },
    { "id": 2, "tasks": ["2.6", "3.1", "4.1", "5.1", "6.1", "7.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.4", "3.5", "3.6", "3.7", "3.8", "3.9", "4.2", "4.3", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9", "5.2", "5.3", "5.4", "5.5", "5.6", "5.7", "5.8", "5.9", "6.2", "6.3", "6.4", "6.5", "6.6", "6.7", "6.8", "7.2", "7.3", "7.4", "7.5", "7.6", "7.7"] },
    { "id": 4, "tasks": ["3.10", "4.10", "5.10", "6.9", "7.8"] },
    { "id": 5, "tasks": ["9.1", "9.2", "9.3", "10.1", "10.2", "11.1"] },
    { "id": 6, "tasks": ["9.4", "9.5", "9.6", "9.7", "9.8", "9.9", "9.10", "10.3", "10.4", "10.5", "10.6", "10.7", "11.2", "11.3", "11.4", "11.5", "11.6"] },
    { "id": 7, "tasks": ["9.11", "10.8", "10.9", "10.10", "10.11", "11.7"] },
    { "id": 8, "tasks": ["12.1", "12.2", "12.3", "12.4", "12.5", "12.6", "12.7"] },
    { "id": 9, "tasks": ["12.8"] }
  ]
}
```

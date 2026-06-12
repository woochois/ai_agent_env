# Requirements Document

## Introduction

klid-aicb React 앱의 플레이그라운드(chatbot) UI와 동일한 기능, 디자인, 기술 스택을 갖춘 React 앱을 구현합니다. klid-aicb와 동일하게 **GraphQL + Relay**를 프론트엔드 데이터 레이어로 사용하며, 백엔드는 FastAPI + Strawberry(GraphQL) + PostgreSQL로 구성합니다. 인증은 JWT 기반 로그인을 구현하고, 모든 데이터는 Docker 컨테이너로 실행되는 PostgreSQL 서버에 영속화합니다.

플레이그라운드는 세 가지 주요 화면으로 구성됩니다:
1. **로그인 화면** — 사용자 인증 (아이디/비밀번호 → JWT 토큰 발급)
2. **챗봇 목록 화면** — 생성된 챗봇들을 카드 그리드로 표시하며, 챗봇 추가/삭제/편집 기능 제공
3. **챗봇 대화 화면** — 특정 챗봇을 선택하여 실시간 AI 대화를 수행하는 채팅 인터페이스

각 챗봇은 독립적인 시스템 프롬프트, 가드레일, 모델 선택, 도구 연결 설정을 가지며, 모든 데이터는 PostgreSQL에 저장됩니다.

## Glossary

- **Playground**: 사용자가 AI 에이전트와 대화할 수 있는 웹 기반 채팅 인터페이스
- **Session**: 하나의 연속된 대화 흐름을 나타내는 단위. 고유 ID, 제목, 메시지 배열로 구성
- **Session_Sidebar**: 세션 목록을 표시하는 좌측 패널. 새 채팅 생성, 세션 선택, 삭제, 접기/펼치기 기능 제공
- **Navigation_Bar**: 앱 좌측의 메인 네비게이션 영역. 대시보드, 에이전트, 플레이그라운드, API 문서 메뉴 포함
- **Chat_Area**: 메시지 표시 및 입력을 담당하는 중앙 영역
- **Message_Bubble**: 사용자 또는 AI 메시지를 시각적으로 표시하는 둥근 컨테이너
- **Tool_Card**: AI가 사용한 도구(SQL, RAG, 웹검색 등)의 결과를 카드 형태로 표시하는 컴포넌트
- **Typing_Indicator**: AI 응답 생성 중임을 나타내는 점 3개 애니메이션
- **Agent_Chip**: 선택 가능한 에이전트를 칩(pill) 형태로 표시하는 UI 요소
- **Theme_Toggle**: 다크 모드와 라이트 모드를 전환하는 버튼
- **Health_Badge**: 서버 연결 상태를 시각적으로 표시하는 뱃지
- **Supervisor_API**: `/agent/supervisor/chat` POST 엔드포인트. 메시지, session_id, tool_agents를 수신하여 응답을 반환
- **Agents_API**: `/agent/supervisor/agents` GET 엔드포인트. 등록된 Tool Agent 목록을 반환
- **Health_API**: `/health` GET 엔드포인트. 서버 상태 정보를 반환
- **LocalStorage**: 브라우저의 Web Storage API. 테마 설정과 JWT 토큰만 저장 (데이터 영속화는 PostgreSQL)
- **GraphQL**: API 쿼리 언어. 프론트엔드가 필요한 데이터만 요청하는 선언적 데이터 페칭
- **Relay**: Meta의 GraphQL 클라이언트. Fragment 기반 데이터 관리, 캐시, 페이지네이션 제공
- **Strawberry**: Python 타입 기반 GraphQL 라이브러리. FastAPI와 통합하여 GraphQL 서버 구현
- **JWT**: JSON Web Token. 인증 토큰으로 로그인 후 모든 API 요청에 Authorization 헤더로 전달
- **PostgreSQL**: Docker 컨테이너로 실행되는 관계형 데이터베이스. 챗봇, 세션, 메시지, 사용자 데이터 영속화
- **Chatbot**: 특정 설정(시스템 프롬프트, 모델, 가드레일, 도구)으로 구성된 AI 대화 에이전트 인스턴스. 플레이그라운드 목록에 카드로 표시됨
- **Chatbot_List**: 생성된 챗봇들을 카드 그리드 형태로 표시하는 메인 플레이그라운드 관리 화면
- **Chatbot_Card**: 개별 챗봇의 제목, 설명을 표시하는 카드 UI. 클릭 시 해당 챗봇의 대화 화면으로 이동
- **Chatbot_Create_Dialog**: 새 챗봇을 생성하기 위한 모달 다이얼로그. 제목, 설명을 입력받음
- **Chatbot_Settings**: 챗봇의 기본 설정, 시스템 프롬프트, 가드레일, 모델, 도구 연결을 구성하는 설정 패널
- **System_Prompt**: 챗봇의 행동을 지시하는 시스템 레벨 프롬프트 텍스트
- **Guardrail**: 챗봇의 응답에서 금지/허용할 내용을 정의하는 안전 규칙
- **Model_Select**: 챗봇이 사용할 LLM 모델을 선택하는 드롭다운. 등록된 모델 목록에서 선택
- **Tool_Connection**: 챗봇에 연결할 Tool Agent를 선택하여 해당 도구를 대화 중 활성화하는 설정

## Requirements

### Requirement 1: 좌측 네비게이션 바

**User Story:** As a 사용자, I want 앱의 주요 기능(대시보드, 에이전트, 플레이그라운드, API 문서)에 빠르게 접근할 수 있는 고정 네비게이션 바, so that 원하는 페이지로 쉽게 이동할 수 있다.

#### Acceptance Criteria

1. THE Navigation_Bar SHALL 뷰포트 좌측에 고정(스크롤과 무관하게 항상 표시)된 256px 너비의 세로 영역으로 표시되며, 상단에 앱 로고, 중앙에 메인 메뉴(대시보드, 에이전트, 플레이그라운드, API 문서), 하단에 테마 토글 버튼 및 헬스 상태 뱃지를 포함한다
2. WHEN 사용자가 네비게이션 메뉴 항목(대시보드, 에이전트, 플레이그라운드)을 클릭하면, THE Navigation_Bar SHALL 해당 항목에 비활성 항목과 구별되는 배경색 및 텍스트 색상을 적용하고, 이전에 활성이던 항목의 활성 스타일을 제거하여 동시에 하나의 항목만 활성 상태로 표시한다
3. WHEN 사용자가 API 문서 메뉴를 클릭하면, THE Navigation_Bar SHALL 새 브라우저 탭에서 FastAPI Swagger UI(`/docs`) 페이지를 열고, 네비게이션 바의 현재 활성 항목 상태는 변경하지 않는다
4. WHEN 테마 토글 버튼을 클릭하면, THE Navigation_Bar SHALL 현재 테마를 다크↔라이트로 전환하고, 선택된 테마를 로컬 저장소에 저장하여 페이지 새로고침 시에도 마지막 선택 테마가 유지되도록 한다
5. THE Navigation_Bar SHALL 헬스 상태 뱃지에 서비스 상태를 "healthy", "degraded", "unhealthy" 중 하나로 표시하며, 30초 간격으로 `/health` 엔드포인트를 호출하여 상태를 갱신한다

### Requirement 2: 세션 관리 사이드바

**User Story:** As a 사용자, I want 이전 대화 세션 목록을 확인하고 관리(생성, 선택, 삭제, 접기), so that 여러 대화를 효율적으로 관리할 수 있다.

#### Acceptance Criteria

1. THE Session_Sidebar SHALL 240px 너비로 표시되며, 상단에 "새 채팅" 버튼과 접기 버튼, 아래에 세션 카드 목록을 최신 생성순(위에서 아래)으로 포함한다
2. WHEN 사용자가 "새 채팅" 버튼을 클릭하면, THE Playground SHALL 현재 세션을 자동 저장(LocalStorage)하고 비활성화한 후, 빈 채팅 화면(환영 메시지)을 표시한다
3. WHEN 사용자가 세션 카드를 클릭하면, THE Playground SHALL 해당 세션의 메시지를 Chat_Area에 로드하고 해당 세션 카드에 시각적 활성 표시(강조 테두리)를 적용하며, 이전 활성 세션 카드의 활성 표시를 제거한다
4. WHEN 사용자가 세션 카드의 삭제 버튼을 클릭하면, THE Session_Sidebar SHALL 해당 세션을 목록에서 즉시 제거하고 LocalStorage에서 삭제한다
5. IF 삭제된 세션이 현재 활성 세션인 경우, THEN THE Playground SHALL 빈 채팅 화면(환영 메시지)을 표시하고 활성 세션을 없음 상태로 설정한다
6. WHEN 사용자가 접기 버튼을 클릭하면, THE Session_Sidebar SHALL 0px 너비로 축소되고, 채팅 영역 좌측 상단에 펼치기 버튼이 표시된다
7. WHEN 사용자가 펼치기 버튼을 클릭하면, THE Session_Sidebar SHALL 240px 너비로 복원되고, 펼치기 버튼이 숨김 처리된다
8. THE Session_Sidebar SHALL 각 세션 카드에 세션 제목을 최대 1줄로 표시하며, 초과 텍스트는 말줄임표(ellipsis)로 처리한다

### Requirement 3: 데이터 영속성 (PostgreSQL)

**User Story:** As a 사용자, I want 모든 대화 데이터가 서버 DB에 저장되기를, so that 어떤 브라우저에서 접속해도 동일한 데이터를 볼 수 있다.

#### Acceptance Criteria

1. THE Playground SHALL 모든 챗봇, 세션, 메시지 데이터를 Docker 컨테이너로 실행되는 PostgreSQL 데이터베이스에 저장한다
2. WHEN 세션이 생성되거나 메시지가 추가되면, THE Playground SHALL GraphQL mutation을 통해 서버에 즉시 영속화한다
3. WHEN 페이지가 로드되면, THE Playground SHALL GraphQL query를 통해 서버에서 데이터를 조회하여 표시한다
4. THE Playground SHALL Docker Compose로 PostgreSQL 서버를 구성하며, `docker-compose up` 명령으로 DB가 자동으로 초기화되도록 한다

### Requirement 4: 채팅 메시지 표시

**User Story:** As a 사용자, I want 대화 내용을 사용자 메시지와 AI 응답으로 시각적으로 구분하여 볼 수 있기를, so that 대화 흐름을 쉽게 파악할 수 있다.

#### Acceptance Criteria

1. THE Chat_Area SHALL 사용자 메시지를 오른쪽 정렬 버블(teal 색상 배경)로, AI 응답을 왼쪽 정렬 마크다운 렌더링 영역으로 표시한다
2. THE Chat_Area SHALL 각 메시지 옆에 사용자(👤) 또는 AI(🤖) 아바타를 표시한다
3. WHEN AI 응답에 마크다운 문법(제목, 목록, 코드 블록, 테이블, 인용, 링크)이 포함되면, THE Chat_Area SHALL marked.js를 사용하여 HTML로 렌더링한다
4. WHEN 메시지 그룹에 마우스를 올리면, THE Chat_Area SHALL 메시지 전송 시각을 "YYYY.MM.DD HH:MM" 형식으로 표시한다

### Requirement 5: 메시지 입력 및 전송

**User Story:** As a 사용자, I want 텍스트를 입력하고 쉽게 전송할 수 있기를, so that AI와 빠르게 대화할 수 있다.

#### Acceptance Criteria

1. THE Chat_Area SHALL 하단에 둥근 디자인(border-radius 24px)의 입력 영역을 표시하며, 최대 5000자까지 입력 가능한 텍스트 입력칸과 전송 버튼을 포함한다
2. WHEN 사용자가 Enter 키를 누르면, THE Chat_Area SHALL 현재 입력 내용을 메시지로 전송한다
3. WHEN 사용자가 Shift+Enter 키를 누르면, THE Chat_Area SHALL 줄바꿈을 삽입하고 메시지를 전송하지 않는다
4. WHILE 입력칸이 비어있거나(공백만 포함된 경우 포함) AI가 응답 생성 중이면, THE Chat_Area SHALL 전송 버튼을 비활성화 상태로 표시하고, 비활성화된 버튼은 클릭에 반응하지 않는다
5. WHEN 메시지가 전송되면, THE Chat_Area SHALL 입력칸을 비우고 높이를 초기 높이(1행)로 초기화한다
6. WHEN 사용자가 텍스트를 입력하면, THE Chat_Area SHALL 입력칸 높이를 내용의 줄 수에 맞게 자동 조절하되 최소 1행(20px) 이상, 최대 144px을 초과하지 않으며, 최대 높이 초과 시 내부 스크롤을 표시한다
7. WHILE IME(한글 등) 조합 중이면, THE Chat_Area SHALL Enter 키 입력을 전송으로 처리하지 않는다
8. IF 메시지 전송 중 서버 연결에 실패하면, THEN THE Chat_Area SHALL 전송 상태를 해제하고 오류를 나타내는 응답 메시지를 표시한다
9. WHEN 사용자가 입력칸이 비어있는 상태에서 Enter 키를 누르면, THE Chat_Area SHALL 메시지를 전송하지 않는다

### Requirement 6: 백엔드 API 연동 (메시지 전송)

**User Story:** As a 사용자, I want 입력한 메시지가 Supervisor Agent로 전달되고 응답을 받을 수 있기를, so that AI 에이전트의 도움을 받을 수 있다.

#### Acceptance Criteria

1. WHEN 메시지가 전송되면, THE Playground SHALL `POST /agent/supervisor/chat`에 `{ message, session_id, tool_agents }` 형태의 JSON 요청을 전송한다
2. WHEN Supervisor_API가 성공 응답(HTTP 200)을 반환하면, THE Playground SHALL 응답의 `response` 필드를 AI 메시지로 표시하고, `tool_calls`와 `sources` 필드를 Tool_Card로 표시한다
3. IF Supervisor_API가 오류 응답(HTTP 4xx 또는 5xx)을 반환하면, THEN THE Playground SHALL 오류 메시지를 AI 응답 위치에 표시한다
4. IF 네트워크 연결에 실패하면, THEN THE Playground SHALL "서버 연결에 실패했습니다. 잠시 후 다시 시도해주세요." 메시지를 표시한다

### Requirement 7: 타이핑 인디케이터 및 소요 시간 표시

**User Story:** As a 사용자, I want AI가 응답을 생성 중임을 시각적으로 확인하고 소요 시간을 알 수 있기를, so that 응답 대기 중에도 시스템이 동작하고 있음을 인지할 수 있다.

#### Acceptance Criteria

1. WHILE Supervisor_API 응답을 대기하는 동안, THE Chat_Area SHALL 점 3개가 순차적으로 위아래로 움직이는 타이핑 애니메이션을 표시한다
2. WHEN Supervisor_API 응답이 도착하면, THE Chat_Area SHALL 타이핑 인디케이터를 제거하고 응답 메시지를 표시한다
3. WHEN AI 응답이 표시되면, THE Chat_Area SHALL 요청부터 응답까지의 소요 시간을 "N.NN초 동안 생각함" 형식으로 메시지 하단에 표시한다

### Requirement 8: 도구(Tool) 결과 카드 표시

**User Story:** As a 사용자, I want AI가 사용한 도구와 참조 문서를 시각적 카드로 확인할 수 있기를, so that AI 응답의 근거를 파악할 수 있다.

#### Acceptance Criteria

1. WHEN Supervisor_API 응답의 `tool_calls` 필드에 값이 존재하면, THE Chat_Area SHALL "사용된 도구" 카드를 표시하며 각 도구 이름을 칩 형태로 나열한다
2. WHEN Supervisor_API 응답의 `sources` 필드에 값이 존재하면, THE Chat_Area SHALL "참조 문서" 카드를 표시하며 각 문서를 목록으로 나열한다
3. THE Tool_Card SHALL teal 색상 테두리와 배경을 갖는 카드 형태로 메시지 하단에 표시된다

### Requirement 9: 다크/라이트 모드 전환

**User Story:** As a 사용자, I want 다크 모드와 라이트 모드를 전환할 수 있기를, so that 환경에 맞는 화면을 사용할 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 테마 토글 버튼을 클릭하면, THE Playground SHALL 현재 테마를 반대 테마(dark↔light)로 전환하고 모든 UI 요소의 색상을 즉시 업데이트한다
2. WHEN 테마가 전환되면, THE Playground SHALL 선택된 테마를 LocalStorage에 저장한다
3. WHEN 페이지가 로드되면, THE Playground SHALL LocalStorage에 저장된 테마를 적용하며, 저장값이 없으면 다크 모드를 기본값으로 사용한다
4. THE Playground SHALL teal/blue 컬러 팔레트를 기반으로 양쪽 테마 모두에서 일관된 디자인을 유지한다

### Requirement 10: 에이전트 선택

**User Story:** As a 사용자, I want 대화에 사용할 Tool Agent를 선택할 수 있기를, so that 특정 도구를 활용한 답변을 받을 수 있다.

#### Acceptance Criteria

1. WHEN 페이지가 로드되면, THE Playground SHALL `GET /agent/supervisor/agents`를 호출하여 등록된 에이전트 목록을 가져온다
2. THE Playground SHALL 각 에이전트를 칩(pill) 형태의 Agent_Chip으로 표시하며, 타입명에서 `_agent` 접미사를 제거하고 밑줄을 공백으로 변환하여 표시한다
3. WHEN 사용자가 Agent_Chip을 클릭하면, THE Playground SHALL 해당 칩을 선택 상태(teal 테두리 및 배경)로 토글하고, 다음 메시지 전송 시 해당 에이전트를 `tool_agents` 배열에 포함한다
4. WHEN 에이전트 토글 영역을 클릭하면, THE Playground SHALL 에이전트 칩 그리드의 표시/숨김을 전환한다
5. IF Agents_API 호출에 실패하면, THEN THE Playground SHALL "에이전트 로드 실패" 메시지를 에이전트 영역에 표시한다

### Requirement 11: 헬스체크 상태 표시

**User Story:** As a 사용자, I want 서버 연결 상태를 실시간으로 확인할 수 있기를, so that 서비스 이용 가능 여부를 인지할 수 있다.

#### Acceptance Criteria

1. WHEN 페이지가 로드되면, THE Playground SHALL `GET /health`를 호출하여 서버 상태를 확인하고 Health_Badge에 표시한다
2. THE Playground SHALL 30초 간격으로 `GET /health`를 반복 호출하여 상태를 갱신한다
3. WHEN Health_API가 `status: "healthy"`를 반환하면, THE Health_Badge SHALL "● 정상" 텍스트를 녹색으로 표시한다
4. WHEN Health_API가 `status: "degraded"`를 반환하면, THE Health_Badge SHALL "● 부분 장애" 텍스트를 노란색으로 표시한다
5. IF Health_API 호출에 실패하거나 `status: "unhealthy"`를 반환하면, THEN THE Health_Badge SHALL "● 연결 실패" 텍스트를 빨간색으로 표시한다

### Requirement 12: 자동 스크롤

**User Story:** As a 사용자, I want 새 메시지가 추가될 때 채팅 영역이 자동으로 스크롤되기를, so that 최신 메시지를 항상 볼 수 있다.

#### Acceptance Criteria

1. WHEN 사용자 메시지가 추가되면, THE Chat_Area SHALL 메시지 영역을 최하단으로 자동 스크롤한다
2. WHEN AI 응답이 표시되면, THE Chat_Area SHALL 메시지 영역을 최하단으로 자동 스크롤한다
3. WHEN 타이핑 인디케이터가 표시되면, THE Chat_Area SHALL 메시지 영역을 최하단으로 자동 스크롤한다

### Requirement 13: React 프로젝트 구성 (GraphQL + Relay)

**User Story:** As a 개발자, I want 플레이그라운드가 klid-aicb와 동일한 기술 스택(Vite + React + TypeScript + Relay + GraphQL)으로 구성되기를, so that 동일한 개발 경험과 코드 패턴을 유지할 수 있다.

#### Acceptance Criteria

1. THE Playground SHALL `frontend/` 디렉토리에 Vite + React + TypeScript 프로젝트로 구성되며, Tailwind CSS와 shadcn/ui 컴포넌트 라이브러리를 사용한다
2. THE Playground SHALL react-relay + relay-runtime으로 GraphQL 데이터 페칭을 구현하며, relay-compiler로 타입 안전한 Fragment/Query를 생성한다
3. THE Playground SHALL 백엔드에 Strawberry GraphQL 서버를 FastAPI에 통합하여 `/graphql` 엔드포인트를 제공한다
4. THE Playground SHALL react-markdown + remark-gfm + rehype-raw로 마크다운을 렌더링한다
5. THE Playground SHALL 개발 서버(vite dev) 실행 시 FastAPI 백엔드로의 API 프록시를 자동 설정한다
6. THE Playground SHALL 빌드 시 `frontend/dist/` 디렉토리에 정적 파일을 생성하며, FastAPI의 StaticFiles로 서빙 가능하다
7. THE Playground SHALL lucide-react 아이콘 라이브러리를 사용하여 klid-aicb와 동일한 아이콘을 제공한다

### Requirement 14: 챗봇 목록 관리 (생성/삭제)

**User Story:** As a 사용자, I want 여러 챗봇을 생성하고 삭제할 수 있기를, so that 용도별로 서로 다른 AI 에이전트를 구성하여 사용할 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 플레이그라운드 메인 화면에 진입하면, THE Chatbot_List SHALL 생성된 챗봇들을 카드 그리드 형태로 표시하며, 각 카드에 챗봇 제목과 설명을 포함한다
2. WHEN 사용자가 "플레이그라운드 추가" 버튼을 클릭하면, THE Playground SHALL Chatbot_Create_Dialog를 표시하여 제목(필수)과 설명(선택)을 입력받는다
3. WHEN 사용자가 Chatbot_Create_Dialog에서 "생성" 버튼을 클릭하면, THE Playground SHALL GraphQL mutation으로 서버에 새 챗봇을 생성하고 Chatbot_List에 즉시 추가한다
4. IF 제목이 비어있는 상태에서 생성을 시도하면, THEN THE Chatbot_Create_Dialog SHALL 유효성 오류를 표시하고 생성을 차단한다
5. WHEN 사용자가 챗봇 카드의 삭제 버튼을 클릭하면, THE Playground SHALL 삭제 확인 다이얼로그를 표시한다
6. WHEN 사용자가 삭제를 확인하면, THE Playground SHALL GraphQL mutation으로 서버에서 해당 챗봇과 관련된 모든 세션 데이터를 삭제하고 Chatbot_List에서 제거한다
7. WHEN 사용자가 챗봇 카드를 클릭하면, THE Playground SHALL 해당 챗봇의 대화 화면(세션 사이드바 + 채팅 영역)으로 전환한다
8. THE Chatbot_List SHALL 챗봇이 없을 때 "플레이그라운드를 추가해보세요" 빈 상태 메시지를 표시한다

### Requirement 15: 챗봇 기본 설정 (제목/설명/모델)

**User Story:** As a 사용자, I want 챗봇의 제목, 설명, 사용할 모델을 설정할 수 있기를, so that 각 챗봇의 용도와 성능을 조정할 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 챗봇 설정 화면에 진입하면, THE Chatbot_Settings SHALL "기본 설정" 탭에 제목, 설명, 모델 선택 필드를 표시한다
2. THE Chatbot_Settings SHALL 모델 선택을 드롭다운(select) 형태로 제공하며, 등록된 모델 목록을 `GET /agent/supervisor/agents`에서 가져오거나 사전 정의된 모델 목록(예: gpt-4o, gpt-4o-mini, claude-3.5-sonnet)을 표시한다
3. WHEN 사용자가 설정을 변경하고 저장 버튼을 클릭하면, THE Chatbot_Settings SHALL GraphQL mutation으로 서버에 변경 사항을 저장하고 성공 토스트 메시지를 표시한다
4. WHEN 메시지가 전송될 때, THE Playground SHALL 해당 챗봇에 설정된 모델명을 Supervisor_API 요청에 포함하여 전송한다
5. THE Chatbot_Settings SHALL 제목 필드에 빈 값을 허용하지 않으며, 빈 값으로 저장 시도 시 유효성 오류를 표시한다

### Requirement 16: 시스템 프롬프트 설정

**User Story:** As a 사용자, I want 각 챗봇에 고유한 시스템 프롬프트를 작성할 수 있기를, so that AI의 역할과 응답 스타일을 맞춤 설정할 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 "프롬프트" 탭을 클릭하면, THE Chatbot_Settings SHALL 여러 줄 텍스트 편집기(textarea)를 표시하여 시스템 프롬프트를 작성/수정할 수 있도록 한다
2. THE Chatbot_Settings SHALL 시스템 프롬프트 편집기에 placeholder로 예시 프롬프트 안내 텍스트를 표시한다
3. WHEN 사용자가 프롬프트를 입력하고 저장하면, THE Chatbot_Settings SHALL GraphQL mutation으로 서버에 해당 챗봇의 system_prompt를 저장한다
4. WHEN 메시지가 전송될 때, THE Playground SHALL 해당 챗봇에 설정된 system_prompt를 Supervisor_API 요청의 `system_prompt` 필드에 포함하여 전송한다
5. IF 시스템 프롬프트가 비어있으면, THEN THE Playground SHALL Supervisor_API 요청에서 system_prompt 필드를 생략하여 기본 프롬프트를 사용한다

### Requirement 17: 가드레일 설정

**User Story:** As a 사용자, I want 챗봇의 응답에 안전 규칙(가드레일)을 설정할 수 있기를, so that 부적절한 응답을 방지할 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 "가드레일" 탭을 클릭하면, THE Chatbot_Settings SHALL 가드레일 규칙 목록과 새 규칙 추가 영역을 표시한다
2. WHEN 사용자가 새 가드레일 규칙을 입력하고 추가 버튼을 클릭하면, THE Chatbot_Settings SHALL 해당 규칙을 목록에 추가하고 GraphQL mutation으로 서버에 저장한다
3. WHEN 사용자가 기존 가드레일 규칙의 삭제 버튼을 클릭하면, THE Chatbot_Settings SHALL 해당 규칙을 목록에서 제거하고 GraphQL mutation으로 서버에서 삭제한다
4. WHEN 메시지가 전송될 때, THE Playground SHALL 가드레일 규칙들을 시스템 프롬프트 앞에 "[가드레일] 다음 규칙을 반드시 준수하세요:" 형태로 자동 삽입하여 전송한다
5. IF 가드레일 규칙이 없으면, THEN THE Playground SHALL 가드레일 관련 텍스트를 시스템 프롬프트에 추가하지 않는다
6. THE Chatbot_Settings SHALL 가드레일 규칙이 없을 때 "규칙을 추가하면 AI의 응답 범위를 제한할 수 있습니다" 안내 메시지를 표시한다

### Requirement 18: 도구(Tool Agent) 연결 설정

**User Story:** As a 사용자, I want 각 챗봇에 사용할 도구 에이전트를 개별적으로 연결할 수 있기를, so that 챗봇마다 다른 도구 조합을 활용할 수 있다.

#### Acceptance Criteria

1. WHEN 사용자가 "도구" 탭을 클릭하면, THE Chatbot_Settings SHALL 등록된 모든 Tool Agent를 체크박스 또는 토글 목록으로 표시하며, 현재 챗봇에 연결된 도구는 활성 상태로 표시한다
2. WHEN 사용자가 도구를 활성화/비활성화하면, THE Chatbot_Settings SHALL GraphQL mutation으로 서버에 변경 사항을 즉시 저장한다
3. WHEN 해당 챗봇에서 메시지가 전송될 때, THE Playground SHALL 챗봇에 연결된 도구만 Supervisor_API 요청의 `tool_agents` 배열에 포함한다
4. IF 등록된 도구가 없으면, THEN THE Chatbot_Settings SHALL "등록된 에이전트가 없습니다" 메시지를 표시한다
5. THE Chatbot_Settings SHALL 각 도구 옆에 도구 유형명을 표시하여 사용자가 어떤 도구인지 식별할 수 있도록 한다

### Requirement 19: 챗봇 설정 UI 탭 네비게이션

**User Story:** As a 사용자, I want 챗봇 설정을 카테고리별 탭으로 구분하여 볼 수 있기를, so that 원하는 설정을 쉽게 찾고 변경할 수 있다.

#### Acceptance Criteria

1. THE Chatbot_Settings SHALL 설정 화면을 "기본 설정", "프롬프트", "가드레일", "도구" 4개 탭으로 구분하여 표시한다
2. WHEN 사용자가 탭을 클릭하면, THE Chatbot_Settings SHALL 해당 탭의 콘텐츠만 표시하고 나머지 탭 콘텐츠를 숨긴다
3. THE Chatbot_Settings SHALL 세션 사이드바의 설정(⚙️) 버튼 또는 챗봇 카드의 설정 메뉴를 통해 접근 가능하다
4. WHEN 사용자가 설정을 변경하지 않고 다른 탭으로 이동하면, THE Chatbot_Settings SHALL 이전 탭의 입력 내용을 유지한다
5. THE Chatbot_Settings SHALL 모달 다이얼로그 또는 사이드 패널 형태로 표시되며, 닫기 버튼을 제공한다

### Requirement 20: 사용자 인증 (로그인/로그아웃)

**User Story:** As a 사용자, I want 아이디와 비밀번호로 로그인하여 내 챗봇과 대화 기록에 안전하게 접근하고 싶다, so that 다른 사용자와 데이터가 분리되고 보안이 유지된다.

#### Acceptance Criteria

1. THE Playground SHALL 로그인 화면을 제공하며, 아이디(username)와 비밀번호(password) 입력 필드와 "로그인" 버튼을 포함한다
2. WHEN 사용자가 유효한 자격증명으로 로그인하면, THE Playground SHALL 서버에서 JWT 토큰을 발급받아 localStorage에 저장하고, 메인 화면(챗봇 목록)으로 이동한다
3. IF 로그인 자격증명이 유효하지 않으면, THEN THE Playground SHALL "아이디 또는 비밀번호가 올바르지 않습니다" 오류 메시지를 표시한다
4. THE Playground SHALL 모든 GraphQL 요청에 Authorization: Bearer {token} 헤더를 포함하여 인증된 요청만 처리한다
5. IF JWT 토큰이 만료되거나 유효하지 않으면, THEN THE Playground SHALL 자동으로 로그인 화면으로 리다이렉트한다
6. WHEN 사용자가 "로그아웃" 버튼을 클릭하면, THE Playground SHALL localStorage에서 토큰을 삭제하고 로그인 화면으로 이동한다
7. THE Playground SHALL 네비게이션 바 하단에 사용자 아바타, 이름, "로그아웃" 버튼을 표시한다

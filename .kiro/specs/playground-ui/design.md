# Design Document

## Overview

klid-aicb React 앱의 플레이그라운드 UI를 동일한 기술 스택과 디자인 패턴으로 재현하는 프로젝트를 구축합니다. klid-aicb와 동일하게 **GraphQL + Relay** 기반의 프론트엔드와 **NestJS + PostGraphile** 기반의 GraphQL 서버를 사용하며, **JWT 인증**을 포함합니다.

기술 스택:
- **Frontend**: Vite + React 18 + TypeScript + Tailwind CSS + shadcn/ui + **Relay (react-relay)** + react-markdown + lucide-react
- **GraphQL Server**: NestJS + PostGraphile + PostgreSQL (klid-aicb-graphql 패턴)
- **Backend Domain**: FastAPI (기존 Supervisor Agent API 유지)
- **Database**: PostgreSQL 16 (Docker)
- **Auth**: JWT (access token + refresh token, localStorage 저장)
- **Infrastructure**: Docker Compose (FastAPI app + PostgreSQL + Elasticsearch + GraphQL server)

## Architecture

### System Architecture

```mermaid
graph TB
    subgraph Frontend["React Frontend (Vite + Relay)"]
        Router[React Router]
        AuthProvider["AuthProvider<br/>(JWT token 관리)"]
        RelayEnv["RelayEnvironmentProvider<br/>(GraphQL client)"]
        Fragments["Relay Fragments<br/>(co-located data)"]
        Mutations["Relay Mutations<br/>(create/update/delete)"]
    end

    subgraph GraphQLServer["NestJS GraphQL Server"]
        PostGraphile["PostGraphile<br/>(자동 CRUD GraphQL)"]
        AuthMiddleware["JWT Auth Middleware"]
        ChatMutation["Custom Mutation<br/>(chat → Supervisor)"]
        PG["PostgreSQL Connection"]
    end

    subgraph DomainServer["FastAPI Domain Server"]
        SupervisorAPI["/agent/supervisor/chat<br/>POST"]
        AgentsAPI["/agent/supervisor/agents<br/>GET"]
        HealthAPI["/health<br/>GET"]
    end

    subgraph Database["PostgreSQL 16 (Docker)"]
        UsersTable[users]
        ChatbotsTable[chatbots]
        SessionsTable[chatbot_sessions]
        MessagesTable[chatbot_messages]
        GuardRulesTable[guard_rulesets]
        ToolAgentsTable[chatbot_tool_agents]
    end

    Frontend -->|"GraphQL (Bearer JWT)"| GraphQLServer
    GraphQLServer -->|REST| DomainServer
    PostGraphile --> PG
    PG --> Database
```


### Request Flow (Chat)

```mermaid
sequenceDiagram
    participant UI as React (Relay)
    participant GQL as GraphQL Server (NestJS)
    participant DB as PostgreSQL
    participant LLM as FastAPI Supervisor

    UI->>GQL: mutation sendChat($input) + Bearer token
    GQL->>GQL: JWT 검증 → userId 추출
    GQL->>DB: Load chatbot settings (prompt, guardrails, tools)
    GQL->>DB: INSERT user message
    GQL->>LLM: POST /agent/supervisor/chat (with settings)
    LLM-->>GQL: { response, tool_calls, sources }
    GQL->>DB: INSERT bot message (with metadata)
    GQL-->>UI: ChatMessage node (Relay store 자동 업데이트)
```

### Authentication Flow

```mermaid
sequenceDiagram
    participant UI as React
    participant GQL as GraphQL Server
    participant DB as PostgreSQL

    UI->>GQL: POST /auth/login { email, password }
    GQL->>DB: Verify credentials (bcrypt)
    GQL-->>UI: { accessToken, refreshToken }
    UI->>UI: localStorage.setItem('access_token', token)
    
    Note over UI,GQL: 이후 모든 GraphQL 요청에 Bearer token 포함
    
    UI->>GQL: GraphQL query (Authorization: Bearer token)
    GQL->>GQL: JWT 검증 → userId 컨텍스트 주입
    GQL->>DB: PostGraphile row-level security (userId 기반)
    GQL-->>UI: Data (해당 사용자 소유 데이터만)
```

### Component Hierarchy

```
App
├── ThemeProvider (localStorage theme)
│   └── AuthProvider (JWT token + RelayEnvironmentProvider)
│       └── BrowserRouter
│           ├── LoginPage (/login)
│           └── ProtectedRoute
│               └── RootLayout
│                   ├── ModernNav (256px left)
│                   └── Routes
│                       ├── ChatbotListPage (/)
│                       │   ├── PageLayout
│                       │   ├── ChatbotList ← useLazyLoadQuery(ChatbotsQuery)
│                       │   ├── ChatbotCreateDialog → useMutation(CreateChatbot)
│                       │   └── ChatbotDeleteDialog → useMutation(DeleteChatbot)
│                       └── ChatbotDetailPage (/chatbot/:id)
│                           ├── ChatbotSessionList ← useFragment(Sessions)
│                           ├── ChatRoom (flex-1)
│                           │   ├── ChatRoomMessages ← useFragment(Messages)
│                           │   │   ├── UserMessage (teal bubble)
│                           │   │   ├── BotMessage (markdown)
│                           │   │   └── ChatRoomTools
│                           │   ├── ChatRoomPending
│                           │   └── ChatRoomInput → useMutation(SendChat)
│                           └── ChatbotSettings (modal) → useMutation(UpdateChatbot)
```

## Components and Interfaces

### GraphQL Schema (PostGraphile 자동 생성 + Custom Mutations)

PostGraphile이 PostgreSQL 테이블에서 자동으로 CRUD GraphQL 스키마를 생성합니다. 추가로 커스텀 뮤테이션을 정의합니다.

```graphql
# === 자동 생성 (PostGraphile) ===

type Chatbot implements Node {
  id: ID!
  chatbotId: Int!
  title: String!
  description: String
  model: String!
  systemPrompt: String
  userId: Int!
  createdAt: Datetime
  isDeleted: Boolean
  
  sessions(first: Int, after: Cursor, orderBy: [ChatbotSessionsOrderBy!]): ChatbotSessionsConnection!
  guardRulesets: [GuardRuleset!]!
  toolAgents: [ChatbotToolAgent!]!
}

type ChatbotSession implements Node {
  id: ID!
  sessionId: String!
  title: String!
  userId: Int!
  chatbotId: Int!
  createdAt: Datetime
  isDeleted: Boolean
  
  messages(first: Int, after: Cursor, orderBy: [ChatbotMessagesOrderBy!]): ChatbotMessagesConnection!
}

type ChatbotMessage implements Node {
  id: ID!
  messageId: Int!
  sessionId: String!
  role: String!
  content: String!
  toolCalls: [String]
  sources: [String]
  elapsedMs: Float
  createdAt: Datetime
}

type GuardRuleset implements Node {
  id: ID!
  chatbotId: Int!
  rule: String!
  orderIndex: Int!
}

type ChatbotToolAgent implements Node {
  id: ID!
  chatbotId: Int!
  toolAgentKey: String!
  isEnabled: Boolean!
}

# === Custom Mutations ===

type Mutation {
  login(input: LoginInput!): LoginPayload!
  refreshToken(input: RefreshTokenInput!): LoginPayload!
  logout: LogoutPayload!
  sendChat(input: SendChatInput!): SendChatPayload!
}

input LoginInput {
  email: String!
  password: String!
}

type LoginPayload {
  accessToken: String!
  refreshToken: String!
  userId: Int!
}

input RefreshTokenInput {
  refreshToken: String!
}

type LogoutPayload {
  success: Boolean!
}

input SendChatInput {
  chatbotId: Int!
  sessionId: String!
  message: String!
}

type SendChatPayload {
  userMessage: ChatbotMessage!
  botMessage: ChatbotMessage!
}
```

### Relay Fragments & Queries (Frontend)

```typescript
// === Queries ===

// ChatbotListQuery
const ChatbotListQuery = graphql`
  query ChatbotListQuery($userId: Int!) {
    chatbots(filter: { userId: { eq: $userId }, isDeleted: { eq: false } }, orderBy: CREATED_AT_DESC) {
      nodes {
        ...ChatbotCard_chatbot
      }
    }
  }
`

// ChatbotDetailQuery
const ChatbotDetailQuery = graphql`
  query ChatbotDetailQuery($chatbotId: Int!) {
    chatbot(chatbotId: $chatbotId) {
      ...ChatbotDetail_chatbot
      ...ChatbotSettings_chatbot
    }
  }
`

// === Fragments ===

const ChatbotCardFragment = graphql`
  fragment ChatbotCard_chatbot on Chatbot {
    chatbotId
    title
    description
    model
    createdAt
  }
`

const ChatbotDetailFragment = graphql`
  fragment ChatbotDetail_chatbot on Chatbot {
    chatbotId
    title
    sessions(first: 50, orderBy: CREATED_AT_DESC, filter: { isDeleted: { eq: false } }) {
      nodes {
        ...SessionCard_session
      }
    }
  }
`

const SessionMessagesFragment = graphql`
  fragment SessionMessages_session on ChatbotSession {
    messages(first: 100, orderBy: CREATED_AT_ASC) {
      nodes {
        ...MessageItem_message
      }
    }
  }
`

const MessageItemFragment = graphql`
  fragment MessageItem_message on ChatbotMessage {
    messageId
    role
    content
    toolCalls
    sources
    elapsedMs
    createdAt
  }
`

// === Mutations ===

const SendChatMutation = graphql`
  mutation SendChatMutation($input: SendChatInput!) {
    sendChat(input: $input) {
      userMessage { ...MessageItem_message }
      botMessage { ...MessageItem_message }
    }
  }
`

const CreateChatbotMutation = graphql`
  mutation CreateChatbotMutation($input: CreateChatbotInput!) {
    createChatbot(input: $input) {
      chatbot { ...ChatbotCard_chatbot }
    }
  }
`
```

### Frontend Relay Environment

```typescript
// src/api/relayEnvironment.ts (klid-aicb 패턴 동일)

import { Environment, Network, RecordSource, Store, RequestParameters, Variables } from 'relay-runtime'

const TOKEN_KEY = 'access_token'
const GRAPHQL_URL = '/graphql'

const getAuthHeaders = (): Record<string, string> => {
  const token = localStorage.getItem(TOKEN_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const graphqlFetch = async (operation: RequestParameters, variables: Variables) => {
  const response = await fetch(GRAPHQL_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({ query: operation.text, variables }),
  })
  
  if (response.status === 401) {
    const refreshed = await handleAuthError()
    if (!refreshed) throw new Error('Authentication failed')
    return graphqlFetch(operation, variables)
  }
  
  return response.json()
}

export const createRelayEnvironment = () =>
  new Environment({
    network: Network.create(graphqlFetch),
    store: new Store(new RecordSource()),
  })

export let relayEnvironment = createRelayEnvironment()
export const resetRelayEnvironment = () => {
  relayEnvironment = createRelayEnvironment()
  return relayEnvironment
}
```

### AuthProvider Component

```typescript
// src/components/auth-provider.tsx (klid-aicb 패턴 참조)

interface AuthContextType {
  isAuthenticated: boolean
  isLoading: boolean
  currentUserId: number | null
  login: (credentials: { email: string; password: string }) => Promise<void>
  logout: () => void
}

// JWT token → localStorage
// RelayEnvironmentProvider 래핑
// 로그인 시 resetRelayEnvironment() (Relay Store 초기화)
// ProtectedRoute: 미인증 → /login 리다이렉트
```

### NestJS GraphQL Server Structure

```
graphql-server/
├── src/
│   ├── main.ts                       # NestJS bootstrap + PostGraphile
│   ├── app.module.ts
│   ├── postgraphile/
│   │   ├── postgraphile.module.ts
│   │   ├── postgraphile.service.ts   # PostGraphile 인스턴스
│   │   └── plugins/
│   │       └── chat-plugin.ts        # sendChat custom mutation
│   ├── features/
│   │   ├── auth/
│   │   │   ├── auth.module.ts
│   │   │   ├── auth.controller.ts    # POST /auth/login, /auth/refresh
│   │   │   └── auth.service.ts       # JWT sign/verify, bcrypt
│   │   └── health/
│   │       └── health.controller.ts
│   └── shared/
│       └── services/
│           └── api-config.service.ts
├── package.json
├── Dockerfile
└── tsconfig.json
```

### Docker Compose (Updated)

```yaml
version: "3.9"

services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      - postgres
      - elasticsearch
    volumes:
      - ./logs:/app/logs

  graphql-server:
    build: ./graphql-server
    ports:
      - "4000:4000"
    environment:
      DATABASE_URL: postgres://user:password@postgres:5432/agent_db
      JWT_SECRET: ${JWT_SECRET:-playground-jwt-secret-key}
      JWT_REFRESH_SECRET: ${JWT_REFRESH_SECRET:-playground-refresh-secret-key}
      DOMAIN_SERVER_URL: http://app:8000
      PORT: 4000
      HOST: 0.0.0.0
    depends_on:
      - postgres
      - app

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
      POSTGRES_DB: agent_db
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql

  elasticsearch:
    image: elasticsearch:8.11.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9200:9200"
    volumes:
      - esdata:/usr/share/elasticsearch/data

volumes:
  pgdata:
  esdata:
```

### UI Components

```
LoginPage           — 이메일/비밀번호 입력 + 로그인 버튼 + 에러 표시
ModernNav           — 256px 좌측 네비게이션 (메뉴, 헬스뱃지, 테마토글)
PageLayout          — 페이지 헤더 (title, description, action) + 콘텐츠
ChatMarkdown        — react-markdown 래퍼 (GFM 테이블, 코드, 인용 스타일링)
TypingIndicator     — 점 3개 bounce 애니메이션
ChatbotListPage     — 카드 그리드 + 생성/삭제 Dialog
ChatbotDetailPage   — 세션 사이드바 + 채팅 영역
ChatbotSessionList  — 240px 세션 목록 (접기/펼치기)
ChatRoom            — 환영 메시지 / 메시지 목록 / 입력
ChatRoomInput       — rounded-3xl Textarea + 전송 버튼
ChatRoomMessages    — 사용자 버블(teal) + AI 마크다운 + 아바타 + 시간
ChatRoomPending     — 타이핑 인디케이터
ChatRoomTools       — tool_calls 칩 + sources 카드
ChatbotSettings     — Tabs Dialog (기본/프롬프트/가드레일/도구)
```

### Directory Structure

```
project/
├── app/                              # FastAPI Domain Server (기존 유지)
│   ├── agents/
│   ├── services/
│   ├── main.py
│   └── ...
├── graphql-server/                   # NestJS + PostGraphile (신규)
│   ├── src/
│   │   ├── main.ts
│   │   ├── app.module.ts
│   │   ├── postgraphile/
│   │   │   ├── postgraphile.module.ts
│   │   │   ├── postgraphile.service.ts
│   │   │   └── plugins/chat-plugin.ts
│   │   ├── features/
│   │   │   ├── auth/ (module, controller, service)
│   │   │   └── health/ (controller)
│   │   └── shared/services/
│   ├── Dockerfile
│   ├── package.json
│   └── tsconfig.json
├── frontend/                         # React + Relay (신규)
│   ├── src/
│   │   ├── api/
│   │   │   ├── relayEnvironment.ts
│   │   │   └── auth.ts
│   │   ├── components/
│   │   │   ├── ui/ (shadcn/ui)
│   │   │   ├── auth-provider.tsx
│   │   │   ├── theme-provider.tsx
│   │   │   ├── modern-nav.tsx
│   │   │   ├── page-layout.tsx
│   │   │   ├── chat-markdown.tsx
│   │   │   └── typing-indicator.tsx
│   │   ├── features/
│   │   │   ├── auth/pages/login-page.tsx
│   │   │   └── chatbot/
│   │   │       ├── components/
│   │   │       ├── __generated__/ (relay-compiler)
│   │   │       └── pages/
│   │   ├── lib/utils.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── relay.config.json
│   ├── schema.graphql
│   ├── vite.config.ts
│   ├── package.json
│   └── dist/
├── db/
│   └── init.sql
├── docker-compose.yml
├── Dockerfile
└── .env
```


## Data Models

### Database Schema (PostgreSQL)

```mermaid
erDiagram
    users {
        serial user_id PK
        varchar user_name
        varchar user_email UK
        varchar user_password
        boolean is_admin
        timestamp created_at
        boolean is_deleted
    }

    models {
        serial model_id PK
        varchar model_name
        varchar provider
        boolean is_active
    }

    chatbots {
        serial chatbot_id PK
        varchar chatbot_title
        varchar description
        boolean chatbot_visibility
        int model_id FK
        text chatbot_prompt
        int user_id FK
        int update_version
        boolean is_deleted
        timestamp created_at
    }
    
    chatbot_sessions {
        varchar session_id PK
        varchar title
        int user_id FK
        int chatbot_id FK
        int update_version
        boolean is_deleted
        timestamp created_at
    }
    
    chatbot_messages {
        serial message_id PK
        varchar session_id FK
        varchar role
        text content
        text_arr tool_calls
        text_arr sources
        float elapsed_ms
        timestamp created_at
    }

    guard_rulesets {
        serial guard_ruleset_id PK
        int chatbot_id FK
        text rule
        int order_index
    }

    chatbot_tool_agents {
        serial id PK
        int chatbot_id FK
        varchar tool_agent_key
        boolean is_enabled
    }

    users ||--o{ chatbots : "owns"
    users ||--o{ chatbot_sessions : "owns"
    chatbots ||--o{ chatbot_sessions : "has many"
    chatbot_sessions ||--o{ chatbot_messages : "has many"
    chatbots ||--o{ guard_rulesets : "has many"
    chatbots ||--o{ chatbot_tool_agents : "has many"
    models ||--o{ chatbots : "used by"
```

### Initial SQL (db/init.sql)

```sql
-- Users table
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    user_name VARCHAR(100) NOT NULL,
    user_email VARCHAR(200) NOT NULL UNIQUE,
    user_password VARCHAR(255) NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    is_deleted BOOLEAN DEFAULT FALSE
);

-- Models table
CREATE TABLE models (
    model_id SERIAL PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- Chatbots table
CREATE TABLE chatbots (
    chatbot_id SERIAL PRIMARY KEY,
    chatbot_title VARCHAR(100) NOT NULL,
    description VARCHAR(500) DEFAULT '',
    chatbot_visibility BOOLEAN DEFAULT FALSE,
    chatbot_plugin_key VARCHAR(100),
    model_id INT REFERENCES models(model_id),
    chatbot_prompt TEXT DEFAULT '',
    user_id INT NOT NULL REFERENCES users(user_id),
    update_version INT DEFAULT 1,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Sessions table
CREATE TABLE chatbot_sessions (
    session_id VARCHAR(50) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    title VARCHAR(200) NOT NULL DEFAULT '새 채팅',
    user_id INT NOT NULL REFERENCES users(user_id),
    chatbot_id INT NOT NULL REFERENCES chatbots(chatbot_id) ON DELETE CASCADE,
    update_version INT DEFAULT 1,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Messages table
CREATE TABLE chatbot_messages (
    message_id SERIAL PRIMARY KEY,
    session_id VARCHAR(50) NOT NULL REFERENCES chatbot_sessions(session_id) ON DELETE CASCADE,
    role VARCHAR(4) NOT NULL CHECK (role IN ('user', 'bot')),
    content TEXT NOT NULL,
    tool_calls TEXT[] DEFAULT '{}',
    sources TEXT[] DEFAULT '{}',
    elapsed_ms DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Guard rulesets table
CREATE TABLE guard_rulesets (
    guard_ruleset_id SERIAL PRIMARY KEY,
    chatbot_id INT NOT NULL REFERENCES chatbots(chatbot_id) ON DELETE CASCADE,
    rule TEXT NOT NULL,
    order_index INT NOT NULL DEFAULT 0
);

-- Chatbot tool agents table
CREATE TABLE chatbot_tool_agents (
    id SERIAL PRIMARY KEY,
    chatbot_id INT NOT NULL REFERENCES chatbots(chatbot_id) ON DELETE CASCADE,
    tool_agent_key VARCHAR(100) NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE
);

-- Indexes
CREATE INDEX idx_chatbots_user_id ON chatbots(user_id);
CREATE INDEX idx_sessions_chatbot_id ON chatbot_sessions(chatbot_id);
CREATE INDEX idx_sessions_user_id ON chatbot_sessions(user_id);
CREATE INDEX idx_messages_session_id ON chatbot_messages(session_id);
CREATE INDEX idx_messages_created_at ON chatbot_messages(created_at ASC);
CREATE INDEX idx_guard_rulesets_chatbot ON guard_rulesets(chatbot_id);
CREATE INDEX idx_tool_agents_chatbot ON chatbot_tool_agents(chatbot_id);

-- Seed: default models
INSERT INTO models (model_name, provider) VALUES
  ('gpt-4o', 'openai'),
  ('gpt-4o-mini', 'openai'),
  ('claude-3.5-sonnet', 'anthropic');

-- Seed: admin user (password: admin123)
INSERT INTO users (user_name, user_email, user_password, is_admin)
VALUES ('Admin', 'admin@playground.local',
  '$2b$10$EixZaYVK1fsbw1ZfbX3OXe.PaWXc0vC3xkLdZo0aHH3h.qQ8H7rCe', TRUE);
```

### Design Decisions

#### PostGraphile vs Custom Resolvers

**Decision**: NestJS + PostGraphile (klid-aicb와 동일)

**Rationale**:
- PostGraphile이 PostgreSQL 테이블에서 자동으로 CRUD GraphQL 스키마 생성
- Relay-compatible Node interface, Cursor-based pagination 자동 지원
- 커스텀 비즈니스 로직(sendChat, auth)만 별도 Plugin/Controller로 추가
- klid-aicb와 완전히 동일한 패턴으로 유지보수 용이

#### JWT Authentication

**Decision**: Access Token + Refresh Token (localStorage 저장)

**Rationale**:
- klid-aicb와 동일한 인증 패턴
- Relay Network layer에서 자동으로 Bearer token 첨부
- 401 응답 시 refresh token으로 재발급 시도 후 재요청
- 로그인 시 resetRelayEnvironment()로 Relay Store 초기화 (계정 분리)

#### Relay vs React Query

**Decision**: Relay (react-relay + relay-compiler)

**Rationale**:
- klid-aicb와 동일한 데이터 패칭 패턴
- Fragment co-location: 각 컴포넌트가 필요한 데이터만 선언
- PostGraphile Node interface와 자연스럽게 연동
- relay-compiler 빌드 시 쿼리 최적화 + 타입 자동 생성
- Optimistic update, Store update 등 mutation 후 UI 갱신이 선언적

#### Data Storage: PostgreSQL (Docker)

**Decision**: LocalStorage 제거 → PostgreSQL 서버사이드 영속화

**Rationale**:
- 다중 디바이스/브라우저에서 데이터 접근 가능
- Docker로 개발 환경 일관성 보장
- PostGraphile이 테이블→GraphQL 자동 변환
- FK, cascade delete 등 DB 수준 데이터 무결성 보장
- LocalStorage는 테마 설정에만 사용

#### Separate Junction Tables vs Arrays

**Decision**: guard_rulesets + chatbot_tool_agents를 별도 테이블로 분리 (klid-aicb 패턴)

**Rationale**:
- klid-aicb 스키마와 동일한 구조
- PostGraphile이 자동으로 관계형 GraphQL 필드 생성
- 개별 규칙의 순서(order_index) 관리 가능
- 도구별 활성/비활성 상태 토글 가능


## Error Handling

| 상황 | 처리 방식 |
|------|-----------|
| 네트워크 실패 (fetch reject) | Toast: "서버 연결에 실패했습니다" |
| GraphQL 에러 (errors[]) | Toast: 에러 메시지 표시 |
| 401 Unauthorized | 자동 refresh token 시도 → 실패 시 /login 리다이렉트 |
| 422 Validation | 인라인 폼 필드 에러 표시 |
| Chat 실패 | AI 응답 위치에 오류 메시지 렌더링 |
| Health API 실패 | 빨간색 뱃지 "● 연결 실패" |
| Agents API 실패 | "에이전트 로드 실패" 메시지 |

## Testing Strategy

- TypeScript strict 모드 (타입 안전성)
- relay-compiler (빌드 타임 쿼리 검증)
- NestJS e2e tests (GraphQL endpoint 테스트)
- React Testing Library + msw (컴포넌트 + API 모킹)
- Docker Compose 기반 통합 테스트

## Correctness Properties

### Property 1: Auth Token Lifecycle
JWT token은 로그인 성공 시 localStorage에 저장되고, 모든 GraphQL 요청의 Authorization 헤더에 포함되며, 로그아웃 시 삭제된다.
**Validates: Requirements 20.2, 20.4, 20.6**

### Property 2: Cascade Delete Integrity
챗봇 삭제 시 해당 챗봇의 모든 세션, 메시지, 가드레일, 도구 연결이 DB에서 cascade 삭제된다.
**Validates: Requirements 14.6**

### Property 3: Chat Message Persistence
sendChat mutation은 반드시 user message와 bot message 모두를 DB에 저장하고, Relay 응답으로 둘 다 반환한다.
**Validates: Requirements 3.2, 6.1, 6.2**

### Property 4: IME-Safe Enter Key
IME 조합 중(isComposing === true) Enter 키는 메시지 전송을 트리거하지 않으며, Shift+Enter는 항상 줄바꿈만 삽입한다.
**Validates: Requirements 5.2, 5.3, 5.7**

### Property 5: User Data Isolation
인증된 사용자는 자신이 소유한 챗봇/세션/메시지만 조회/수정/삭제할 수 있으며, 다른 사용자의 데이터에 접근할 수 없다.
**Validates: Requirements 20.4**

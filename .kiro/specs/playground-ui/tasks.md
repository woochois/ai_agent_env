# Implementation Plan:

## Overview

klid-aicb와 동일한 기술 스택(GraphQL + Relay + NestJS + PostGraphile + PostgreSQL + JWT 인증)으로 플레이그라운드 UI를 구축합니다. 3개의 서비스(FastAPI, NestJS GraphQL, PostgreSQL)를 Docker Compose로 오케스트레이션합니다.

## Tasks

- [x] 1. 데이터베이스 스키마 및 Docker 설정: PostgreSQL 초기화 SQL(users, models, chatbots, chatbot_sessions, chatbot_messages, guard_rulesets, chatbot_tool_agents 테이블 + 인덱스 + 시드 데이터), Docker Compose에 postgres 서비스 추가 및 init.sql 마운트 [Requirement 3, 20]
  - [x] 1.1 `db/init.sql` 생성 (테이블, 인덱스, CHECK 제약, 시드 데이터)
  - [x] 1.2 `docker-compose.yml` 업데이트 (postgres, graphql-server 서비스 추가)

- [ ] 2. NestJS GraphQL 서버 초기 설정: `graphql-server/` 디렉토리에 NestJS 프로젝트 생성, PostGraphile 연동, 기본 모듈 구성, Dockerfile [Requirement 13]
  - [-] 2.1 NestJS 프로젝트 생성 (main.ts, app.module.ts, package.json, tsconfig.json)
  - [ ] 2.2 PostGraphile 모듈 (postgraphile.module.ts, postgraphile.service.ts) - DB 연결 + GraphQL 스키마 자동 생성
  - [ ] 2.3 Dockerfile 생성

- [ ] 3. JWT 인증 구현 (NestJS): Auth 모듈(login, refresh, logout 엔드포인트), bcrypt 비밀번호 검증, JWT sign/verify, Auth middleware (GraphQL 요청에서 Bearer token 검증 → userId 컨텍스트 주입) [Requirement 20]
  - [ ] 3.1 auth.module.ts, auth.controller.ts (POST /auth/login, /auth/refresh)
  - [ ] 3.2 auth.service.ts (JWT 생성/검증, bcrypt verify)
  - [ ] 3.3 Auth Guard/Middleware (GraphQL 요청 Bearer token 검증)

- [ ] 4. sendChat 커스텀 뮤테이션 (NestJS): PostGraphile 플러그인으로 sendChat mutation 구현 - 챗봇 설정 로드 → user 메시지 저장 → FastAPI Supervisor 호출 → bot 메시지 저장 → 결과 반환 [Requirement 6, 7, 16, 17]
  - [ ] 4.1 `plugins/chat-plugin.ts` 구현 (PostGraphile makeExtendSchemaPlugin)
  - [ ] 4.2 Supervisor API 호출 로직 (system_prompt + guardrails 조합, tool_agents 포함)
  - [ ] 4.3 메시지 저장 및 소요시간 측정

- [ ] 5. React 프론트엔드 프로젝트 초기 설정: `frontend/` 디렉토리에 Vite + React + TypeScript + Tailwind + shadcn/ui + Relay 설정, relay.config.json, schema.graphql, vite-plugin-relay [Requirement 13]
  - [ ] 5.1 Vite 프로젝트 생성 + 핵심 의존성 설치 (react-relay, relay-runtime, relay-compiler, vite-plugin-relay, tailwindcss, shadcn/ui, lucide-react, sonner, react-markdown)
  - [ ] 5.2 relay.config.json, schema.graphql (PostGraphile 서버에서 추출), vite.config.ts (proxy + relay plugin)
  - [ ] 5.3 Tailwind CSS + CSS 변수 테마 설정, components.json, src/lib/utils.ts

- [ ] 6. Relay Environment 및 인증 계층: relayEnvironment.ts(GraphQL fetch + Bearer token + 401 자동 refresh), AuthProvider(login/logout/token 관리), ProtectedRoute [Requirement 13, 20]
  - [ ] 6.1 `src/api/relayEnvironment.ts` (Relay Network layer with JWT)
  - [ ] 6.2 `src/components/auth-provider.tsx` (AuthContext, login/logout, localStorage token)
  - [ ] 6.3 `src/features/auth/pages/login-page.tsx` (로그인 폼 + 에러 표시)

- [ ] 7. 공통 컴포넌트: ThemeProvider, ModernNav(256px, 메뉴, 헬스뱃지, 로그아웃, 테마토글), PageLayout, ChatMarkdown, TypingIndicator [Requirement 1, 4, 7, 9, 11, 20]
  - [ ] 7.1 `src/components/theme-provider.tsx` (다크/라이트, localStorage)
  - [ ] 7.2 `src/components/modern-nav.tsx` (메뉴 항목, 헬스뱃지, 사용자 아바타, 로그아웃 버튼)
  - [ ] 7.3 `src/components/page-layout.tsx`
  - [ ] 7.4 `src/components/chat-markdown.tsx` (react-markdown + rehype-raw + remark-gfm)
  - [ ] 7.5 `src/components/typing-indicator.tsx`

- [ ] 8. 라우팅 및 앱 진입점: App.tsx(ThemeProvider + AuthProvider + RelayEnvironmentProvider + Router + Toaster), Routes(/login, /, /chatbot/:id) [Requirement 13, 20]
  - [ ] 8.1 src/main.tsx + src/App.tsx (provider 스택)
  - [ ] 8.2 라우트 설정 (react-router-dom: /login, /, /chatbot/:id)

- [ ] 9. 챗봇 목록 화면 (Relay): ChatbotListPage(useLazyLoadQuery → ChatbotsQuery), ChatbotCard(useFragment), ChatbotCreateDialog(useMutation → CreateChatbot), ChatbotDeleteDialog(useMutation → DeleteChatbot) [Requirement 14]
  - [ ] 9.1 GraphQL queries/mutations + relay-compiler 실행
  - [ ] 9.2 chatbot-list-page.tsx + chatbot-list.tsx (카드 그리드, 빈 상태)
  - [ ] 9.3 chatbot-create-dialog.tsx + chatbot-delete-dialog.tsx (mutations)

- [ ] 10. 챗봇 대화 화면 - 세션 사이드바 (Relay): ChatbotDetailPage(useLazyLoadQuery), ChatbotSessionList(useFragment + usePaginationFragment), 새 채팅(useMutation), 세션 삭제(useMutation), 접기/펼치기 [Requirement 2]
  - [ ] 10.1 chatbot-detail-page.tsx (쿼리 + 레이아웃)
  - [ ] 10.2 chatbot-session-list.tsx (Fragment, pagination, 접기/펼치기)
  - [ ] 10.3 세션 생성/삭제 mutations + Relay store update

- [ ] 11. 채팅 영역 (Relay): ChatRoom(환영/메시지), ChatRoomMessages(useFragment → 메시지 목록), ChatRoomPending(타이핑), ChatRoomTools(tool_calls/sources), ChatRoomInput(Enter/Shift+Enter/IME), useMutation(SendChat) + Relay store update [Requirement 4, 5, 6, 7, 8, 12]
  - [ ] 11.1 chat-room.tsx + chat-room-messages.tsx (Relay Fragment, 자동 스크롤)
  - [ ] 11.2 chat-room-input.tsx (Enter/Shift+Enter/IME, 자동높이, disabled)
  - [ ] 11.3 chat-room-pending.tsx + chat-room-tools.tsx
  - [ ] 11.4 SendChat mutation + optimistic update + Relay connection update

- [ ] 12. 챗봇 설정 (Relay): ChatbotSettings Dialog(Tabs: 기본/프롬프트/가드레일/도구), UpdateChatbot mutation, guardrails CRUD mutations, tool_agents 토글 mutations [Requirement 15, 16, 17, 18, 19]
  - [ ] 12.1 chatbot-settings.tsx (Dialog + Tabs)
  - [ ] 12.2 chatbot-settings-basic.tsx (title, description, model Select)
  - [ ] 12.3 chatbot-settings-prompt.tsx (Textarea)
  - [ ] 12.4 chatbot-settings-guard.tsx (규칙 CRUD)
  - [ ] 12.5 chatbot-settings-tool.tsx (에이전트 Switch 토글)

- [ ] 13. 에이전트 선택 & 헬스체크: 에이전트 칩 영역(GET /agent/supervisor/agents → fetch), 헬스체크 뱃지(GET /health → 30초 polling) [Requirement 10, 11]
  - [ ] 13.1 에이전트 칩 선택 UI (REST API fetch, 별도 hook)
  - [ ] 13.2 헬스체크 뱃지 (30초 interval polling)

- [ ] 14. 빌드 및 통합: frontend 빌드 → FastAPI 서빙, schema.graphql 추출 자동화, docker-compose up으로 전체 스택 가동 확인 [Requirement 13]
  - [ ] 14.1 frontend/package.json 빌드 스크립트 + relay-compiler
  - [ ] 14.2 app/main.py 수정 (frontend/dist/ StaticFiles 서빙)
  - [ ] 14.3 docker-compose up 전체 스택 통합 테스트

## Task Dependency Graph

```json
{
  "waves": [
    {"tasks": ["1"]},
    {"tasks": ["2", "5"]},
    {"tasks": ["3", "6"]},
    {"tasks": ["4", "7", "8"]},
    {"tasks": ["9", "13"]},
    {"tasks": ["10"]},
    {"tasks": ["11", "12"]},
    {"tasks": ["14"]}
  ]
}
```

## Notes

- klid-aicb와 동일하게 GraphQL + Relay + PostGraphile을 사용하여 코드 패턴 완전 일치
- NestJS GraphQL 서버가 PostGraphile로 CRUD를 자동 생성하고, sendChat은 커스텀 플러그인으로 구현
- 인증은 JWT(access + refresh token) 방식이며, Relay Network layer에서 자동 처리
- 모든 데이터는 Docker PostgreSQL에 영속화되며, LocalStorage는 JWT 토큰과 테마 설정에만 사용
- PostGraphile이 Relay-compatible Node interface와 Cursor-based pagination을 자동 지원

# Phase 0 변경 로그 — AI 에이전트를 모든 것이 가능한 상태로

날짜: 2026-04-04

---

## 요약

개발 하네스(자동 Codex 파이프라인)로 5개 기능 브랜치 구현.
목표: "제한된 도구 실행기"에서 "모든 요청을 처리할 수 있는 AI 에이전트"로 전환.

| 브랜치 | 시도 | 새 테스트 | 상태 |
|--------|------|----------|------|
| `feat/expanded-permissions` | 1회 | 7개 | 완료 |
| `feat/orchestrator-dynamic` | 1회 | 6개 | 완료 |
| `feat/mcp-client` | 2회 | 6개 | 완료 |
| `feat/browser-auto` | 1회 | 8개 | 완료 |
| `feat/google-api-drivers` | 1회 | 8개 | 완료 |

새 테스트 35개 추가. 모든 실행에서 회귀 제로.

---

## 기능 1: 실행 범위 확장

**브랜치**: `feat/expanded-permissions`

### 변경 전
- Shell: `ls`, `pwd`, `echo` 3개만 허용
- 파일: `/tmp`과 앱 데이터 디렉토리만 접근 가능

### 변경 후
- Shell: 24개 명령 허용 — `pip`, `npm`, `node`, `python3`, `git`, `curl`, `wget`, `cat`, `grep`, `find`, `mkdir`, `cp`, `mv`, `touch`, `head`, `tail`, `wc`, `sort`, `uniq`, `diff`
- 파일: 사용자 홈 디렉토리 + 프로젝트 루트까지 확장
- 위험 평가: `shlex.split()` 파싱, 명령별 세분화된 위험 레벨
- 차단 유지: `rm -rf`, `sudo`, `| bash`, `| sh`

---

## 기능 2: 동적 오케스트레이터

**브랜치**: `feat/orchestrator-dynamic`

### 변경 전
- 직선 순차 실행만 가능
- 스텝 간 데이터 전달 불가
- AI 리뷰 1회 제한

### 변경 후
- **조건부 스텝**: `condition="${steps[0].result.success}"` → false면 건너뜀
- **템플릿 파라미터**: `"${steps[0].result.data.url}"` → 런타임에 실제 값으로 치환
- **중첩 참조**: `${steps[0].result.data.items[0]}` 배열 인덱싱 지원
- **안전 폴백**: 잘못된 템플릿 참조는 빈 문자열로, 크래시 없음
- **AI 리뷰 예산**: 1회 → 3회로 증가

---

## 기능 3: MCP 클라이언트 통합

**브랜치**: `feat/mcp-client`

### 변경 전
- MCP가 연결 레지스트리에 "planned"로만 존재
- MCP 프로토콜 구현 없음

### 변경 후
- **MCPClient**: stdio 전송 방식의 MCP 서버 연결 (JSON-RPC 2.0)
  - `list_tools()` — 서버의 사용 가능한 tool 조회
  - `call_tool(name, arguments)` — tool 호출 및 결과 반환
- **MCPTool**: tool 레지스트리에 `mcp`로 등록
  - `run({"server": "name", "tool": "tool_name", "arguments": {...}})`
- 레지스트리 상태: `planned` → `configurable`

### 영향
하나의 통합으로 무한한 외부 도구 사용 가능. Google Calendar MCP 서버 설정 → AI가 일정 생성. Gmail MCP 서버 설정 → AI가 메일 발송.

---

## 기능 4: Playwright 브라우저 자동화

**브랜치**: `feat/browser-auto`

### 변경 전
- Crawler: HTTP fetch만 (JavaScript 불가, 상호작용 불가)
- Browser: URL 검증 후 링크만 반환

### 변경 후
- **BrowserAutoTool**: Playwright 기반 실제 브라우저 자동화
  - `navigate` — 페이지 로드, URL/제목/상태 반환
  - `extract_text` — 텍스트 추출 (최대 10,000자)
  - `click` — CSS 셀렉터로 요소 클릭
  - `type` — CSS 셀렉터로 텍스트 입력
  - `screenshot` — PNG 스크린샷 (/tmp에 저장)
- Headless Chrome 기본, 설정 가능
- 액션당 30초 타임아웃

### 영향
JavaScript 사이트 조작 가능: 네이버 쇼핑 검색, 폼 입력, 동적 콘텐츠 추출, 스크린샷.

---

## 기능 5: Google Calendar + Gmail 실제 API 연동

**브랜치**: `feat/google-api-drivers`

### 변경 전
- Google Calendar: 템플릿 URL 링크만 생성
- Gmail: 시스템에 등록만 되어있고 드라이버 없음
- OAuth 흐름 없음

### 변경 후

**OAuth 모듈** (`connections/oauth.py`):
- 인증 코드 → 액세스/리프레시 토큰 교환
- 자동 토큰 갱신 (30초 버퍼)
- `secret_store`에 안전 저장 (config_store나 일반 파일 아님)

**Google Calendar 드라이버** (강화):
- OAuth 토큰 → 실제 Calendar API 호출 (`events.insert`)
- 토큰 없으면 기존 링크 방식으로 폴백 (하위 호환)

**Gmail 드라이버** (신규):
- `send_email` — MIME 메시지 생성 → Gmail API 발송
- `read_email` — 메시지 목록 조회 (제목, 발신자, 요약)

---

## 변경 전 vs 변경 후

| 요청 | 변경 전 | 변경 후 |
|------|--------|--------|
| "캘린더에 내일 3시 회의 추가" | Google Calendar 링크 | **실제 이벤트 생성** (API) |
| "메일 보내줘" | mailto: 링크 | **실제 Gmail 발송** (API) |
| "네이버 쇼핑에서 최저가" | HTTP fetch (JS 실패) | **Playwright로 실제 결과 추출** |
| "스크린샷 찍어줘" | 불가능 | **Playwright 스크린샷** |
| "git status" | 차단 | **허용** (low risk) |
| "curl API 호출" | 차단 | **허용** (medium, 승인 필요) |
| "MCP 서버 tool 호출" | 불가능 | **MCPTool로 라우팅** |
| 멀티스텝 (검색→메일) | 파라미터 고정 | **${steps[0].result}로 동적 전달** |

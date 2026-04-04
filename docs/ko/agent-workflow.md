# 에이전트 작업 흐름

사용자 입력부터 최종 실행까지 AI 요청이 시스템을 통과하는 흐름.

---

## 전체 흐름

```text
사용자 명령 ("캘린더에 내일 3시 회의 추가해줘")
    │
    ▼
┌──────────────────────────────────────────────┐
��  1. GATEWAY  (FastAPI)                       │
│     인증 → 속도 제한 → 라우팅                    │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  2. INTENT ROUTER                            │
│     규칙 (YAML + 플러그인) → 비AI 매칭?          │
│     ├── YES → Task 생성, used_ai=false        │
│     └── NO  → AI 에이전트가 스텝 계획            │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  3. RISK EVALUATOR                           │
│     각 스텝 → low / medium / high             │
│     medium/high → 승인 필요                    │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  4. ORCHESTRATOR                             │
│     순차 스텝 실행 루프:                         │
│     ┌─ 스텝 실행                               │
│     ├─ 품질 평가                               │
│     ├─ AI 리뷰 (예산: 3회)                      │
│     ├─ ${template} 파라미터 치환                 │
│     ├─ 스텝 조건 평가                           │
│     └─ 재시도/연속 스텝 삽입                      │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  5. TOOLS / PLUGINS / CONNECTORS             │
│     file, shell, crawler, time, system_info  │
│     browser, browser_auto (Playwright)       │
│     mcp (외부 MCP 서버)                        │
│     calendar_helper, gmail, shopping 등       │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  6. RESULT + SUMMARY                         │
│     요약 → 알림 → DB 저장                       │
└──────────────────────────────────────────────┘
```

---

## 1단계: Gateway

사용자가 `POST /command`로 `{"command": "..."}` 전송.
로컬 요청은 인증 없이 통과, 원격은 페어링 토큰 필요.

---

## 2단계: Intent Router

**비AI 경로를 먼저 시도**:

```text
1. 사용자 커스텀 명령 (등록된 트리거)
2. YAML 규칙 (정규표현식 → 툴 + 파라미터)
3. 플러그인 규칙 (각 플러그인이 등록한 패턴)
4. 의도 정규화 (한국어 NLP: URL, 시간, 서비스 감지)
5. ── 위 모두 실패 ──
6. AI 명확화 질��� (요청이 모호한가?)
7. AI 에이전트 계획 (스텝 생성)
8. AI 브라우저/자동화 보조 (폴백 분류기)
9. 최후 수단: Google 검색 링크
```

**출력**: `Task(steps=[Step(tool, params, description)])`

---

## 3단계: 위험 평가

| 툴 | 위험 수준 |
|-----|---------|
| time, system_info, file(read), crawler | low |
| git, cat, grep, find | low |
| curl, wget, pip install | medium |
| file(write/delete), browser_auto, mcp | medium |

medium/high → 사용자 승인 후 실행.

---

## 4단계: 오케스트레이터

### 기본 실행
스텝을 순차적으로 실행하며 각 결과의 품질을 평가.

### 조건부 실행
```python
Step(tool="crawler", params={...}, condition="${steps[0].result.success}")
# → step 0이 성공했을 때만 실행
```

### 동적 파라미터 템플릿
```python
Step(tool="browser", params={"url": "${steps[0].result.data.url}"}, param_template=True)
# → 이전 스텝 결과의 실제 값으로 치환
```

### AI 리뷰 및 연속
- 품질 평가 → 부족하면 AI 리뷰어 판단 (예산: 3회)
- 불합격 → AI가 연속 스텝 계획 → 삽입 후 계속 실행

---

## 5단계: 도구 및 커넥터

| 도구 | 기능 |
|------|------|
| `file` | 파일 읽기/쓰기/복사/이동/삭제 |
| `shell` | 화이트리스트 쉘 명령 실행 (24개) |
| `crawler` | HTTP 페이지 가져오기 + 파싱 |
| `browser` | URL 검증 + 링크 준비 |
| `browser_auto` | **Playwright**: 페이지 이동, 클릭, 입력, 스크린샷, 텍스트 추출 |
| `mcp` | **MCP 프로토콜**: 외부 MCP 서버의 tool 호출 |

### 커넥션 기반 실행 흐름

```text
플러그인이 파싱된 명령 수신
  → connection_manager.execute_capability("create_calendar_event", payload)
  → 매니저가 준비된 드라이버 탐���
     ├── GoogleCalendarDriver (OAuth → 실제 Calendar API)
     ├── TemplateDriver (URL 링크 생성)
     └── MCP 클라이언트 (MCP 서버로 라우팅)
  → 결과를 플러그인에 반환
```

---

## 6단계: 결과 및 요약

모든 스텝 완료 후:
1. AI 요약기가 자연어 요약 생�� (used_ai=true인 경우)
2. 비AI 요약기가 핵심 데이터 추출 (used_ai=false인 경우)
3. SQLite에 상태, 결과, 로그 저장
4. 모바일 알림 큐에 추가 (해당하는 경우)

---

## 예시: 캘린더 일정 추가

```text
"내일 오후 3시 팀 회의 캘린더에 추가해줘"

1. Gateway → POST /command
2. Router → 플러그인 규칙 매칭: calendar_helper (used_ai=false)
3. Risk → low
4. Orchestrator → calendar_helper.run()
   → 파싱: title="팀 회의", datetime=내일 15:00
   → connection_manager → GoogleCalendarDriver
   → OAuth 토큰 있으면: 실제 Calendar API로 이벤트 생성
   → 없으면: Google Calendar 템플릿 링크 반환
5. Quality → sufficient
6. Summary → "내일 15시에 팀 회의 일정을 추가했습니다."
```

## 예시: 멀티스텝 검색 + 메일

```text
"네이버에서 드럼스틱 최저가 검색해서 결과를 메일로 보내줘"

1. Gateway → POST /command
2. Router → 규칙 매칭 실패 → AI 계획:
   Step 1: browser_auto(navigate, naver shopping URL)
   Step 2: browser_auto(extract_text), param_template=True
   Step 3: mcp(server="gmail", tool="send_email",
               arguments={body: "${steps[1].result.data.text}"}),
           condition="${steps[1].result.success}"
3. Risk → medium (브라우저 + 외부 호출)
4. Orchestrator:
   → Step 1: Playwright가 네이버 쇼핑 이동
   → Step 2: 검색 결과 텍스트 추출
   → Step 3: 조건 확인(step 1 성공?) → 템플릿 치환 → Gmail로 발송
5. Summary → "검색 결과를 메일로 발송했습니다."
```

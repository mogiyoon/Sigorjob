# Modules

## 모듈 역할 분리 원칙

- 각 모듈은 가능한 한 단일 책임만 가진다
- HTTP 경로는 `gateway/`에서 받고, 실행은 `intent/`와 `orchestrator/`를 통해 흘린다
- AI 코드는 `ai/`에만 둔다
- 현재 구현 문서는 "이미 있는 것" 기준으로 설명한다

## 모듈별 책임

### `gateway/`

- FastAPI 앱 생성과 lifespan 관리
- CORS, 인증 미들웨어 적용
- HTTP 요청 수신 및 응답
- 로컬 전용 엔드포인트와 원격 엔드포인트 노출
- 정적 프론트엔드 서빙

현재 구현된 주요 라우트:

- `/command`
- `/tasks`
- `/task/{task_id}`
- `/task/{task_id}/retry`
- `/task/{task_id}/continue-ai`
- `/task/{task_id}` `DELETE`
- `/tasks/delete`
- `/tools`
- `/approvals`
- `/approval/{task_id}`
- `/schedule`
- `/schedules`
- `/schedule/{schedule_id}` `DELETE`
- `/pair/data`
- `/pair/status`
- `/pair/rotate`
- `/setup/status`
- `/setup/connections`
- `/setup/connections/{connection_id}`
- `/setup/permissions`
- `/setup/ai`
- `/setup/ai/verify`
- `/setup/tunnel`
- `/setup/cloudflare`
- `/setup/quick`
- `/widget/summary`
- `/mobile/notifications`
- `/mobile/notifications/ack`
- `/mobile/notifications/test`

### `intent/`

- 규칙 테이블(`rules.yaml`) 기반 명령 매칭
- 첫 Step에 대해 가벼운 AI preflight 점검 가능
- 규칙 미매칭 시에만 `ai/agent.py` 호출
- 실행 가능한 `Task`와 `Step` 목록 생성
- 단순 위험도 평가 기반 승인 필요 여부 계산

### `orchestrator/`

- `Task` 상태 관리
- Step 순차 실행
- Tool 조회 및 호출
- Task 결과 저장
- 실행 로그 저장
- 결과 요약 호출
- 마지막 결과에 대한 AI postflight 점검
- 약한 최종 결과를 AI continuation으로 handoff 가능
- 승인 필요 상태 저장과 승인 후 재실행

현재는 단순 순차 실행기이며, Task Graph와 재시도는 아직 없다.

### `ai/`

- `agent.py`: 규칙으로 처리되지 않는 요청의 실행 계획 생성
- `reviewer.py`: 처음/마지막 단계 점검과 품질 리뷰 담당
- `summarizer.py`: 실행 결과를 짧은 자연어로 요약

중요한 점:

- `anthropic_api_key`가 없으면 AI 호출 없이 비AI 폴백으로 동작한다
- AI는 기본 실행 경로가 아니라 보조 경로다

### `tools/`

현재 기본 Tool:

- `file`
- `shell`
- `crawler`
- `time`
- `system_info`

아직 구현되지 않은 예시 Tool:

- `calendar`
- `message`

### `policy/`

- 차단 명령/차단 패턴 검사
- 파일 접근 허용 범위 검사
- 내부 민감 파일 접근 차단
- 정책 차단과 단순 위험도 기반 승인 요청을 함께 사용

### `db/`

- `Task`, `TaskLog`, `ApprovalRequest`, `Schedule` 저장
- SQLite 사용

### `scheduler/`

- APScheduler 기반 반복 작업 등록 및 로드
- cron 스케줄에 따라 명령 실행
- 실행 시 기존 `intent -> orchestrator -> tools` 흐름 재사용

### `tunnel/`

- `cloudflared` 프로세스 시작/종료
- 터널 URL 파싱
- 페어링 토큰 생성/검증/회전
- 패키징된 데스크톱 앱에서는 런타임에 선택된 로컬 백엔드 주소를 따라감

### `cli.py`

- `serve`: FastAPI 서버 실행
- `run`: 단일 명령 실행
- `repl`: 대화형 CLI
- `tools`: 등록된 Tool 출력

## 현재 의존 흐름

```text
gateway -> intent -> orchestrator -> tools
intent -> ai
intent -> ai.reviewer
orchestrator -> ai.summarizer
orchestrator -> ai.reviewer
orchestrator -> db
gateway -> tunnel
gateway -> config
cli -> intent -> orchestrator -> tools
scheduler -> intent -> orchestrator -> tools
```

## 아직 구현되지 않은 계획 항목

- WebSocket 실시간 업데이트
- 다단계 의존 그래프 실행
- JWT 인증

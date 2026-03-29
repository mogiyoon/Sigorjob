# Folder Structure

## 전체 구조

핵심 구조는 아래와 같다.

```text
Agent/
├── backend/        # FastAPI 백엔드, CLI, 오케스트레이션, Tool
├── frontend/       # Next.js 웹 UI
├── mobile/         # React Native WebView 래퍼
├── src-tauri/      # 데스크톱 셸
├── scripts/        # 개발/빌드/CLI 실행 스크립트
└── docs/           # 문서
```

## 주요 폴더

### `backend/`

- `main.py`: 통합 진입점 (`serve/run/repl/tools`)
- `cli.py`: GUI 없는 서버용 CLI
- `gateway/routes/`: HTTP 엔드포인트
- `intent/`: 규칙 매칭과 AI 폴백
- `orchestrator/`: Task 실행
- `tools/`: 개별 Tool 구현
- `scheduler/`: 반복 작업 실행
- `tunnel/`: Cloudflare Tunnel 및 페어링 토큰 관리
- `db/`: SQLite 모델과 세션

### `frontend/`

- `src/app/page.tsx`: 메인 화면
- `src/app/pair/page.tsx`: 모바일 연결 정보 표시
- `src/app/setup/page.tsx`: Cloudflare 설정
- `src/components/ApprovalPanel.tsx`: 승인 대기 작업 UI
- `src/components/SchedulePanel.tsx`: 스케줄 UI

### `mobile/`

- `App.tsx`: 화면 전환
- `QRScanScreen.tsx`: QR 스캔
- `ManualPairScreen.tsx`: 수동 URL/토큰 입력
- `MainScreen.tsx`: WebView 래퍼

### `src-tauri/`

- `main.rs`: release에서 Python sidecar 자동 시작

## 폴더별 핵심 원칙

| 폴더 | 역할 | AI 사용 |
|------|------|---------|
| `gateway/` | 요청 수신/인증/노출 경계 | 없음 |
| `intent/` | 규칙 매칭 우선, 실패 시 AI 호출 | 조건부 |
| `orchestrator/` | 실행 순서/상태 관리, 승인 대기 저장, 결과 저장, 요약 호출 | 없음 |
| `ai/` | 의도 해석과 결과 요약에만 사용 | 조건부 |
| `tools/` | 각 Tool은 독립 플러그인 | Tool별 |
| `policy/` | 허용/차단 규칙 검사 | 없음 |
| `scheduler/` | cron 기반 반복 작업 실행 | 없음 |
| `tunnel/` | 외부 접속용 터널 상태 및 페어링 토큰 관리 | 없음 |
| `cli.py` | GUI 없는 서버용 실행 진입점 | 없음 |

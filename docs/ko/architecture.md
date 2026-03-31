# Architecture

## 개요

이 프로젝트는 로컬 PC를 실행 허브로 사용하는 자동화 플랫폼이다.
사용자는 웹, 모바일, CLI를 통해 명령을 보내고,
시스템은 가능한 한 규칙 기반 자동화로 처리하며
AI는 꼭 필요한 판단 지점에서만 개입한다.

핵심 방향:

- 기본 실행 경로는 비AI 자동화
- AI 최소 사용은 비용 절감이 아니라 제품 차별점
- 로컬 PC가 실제 실행 주체
- 모바일은 얇은 WebView 리모컨
- GUI 없는 서버에서는 CLI로 같은 백엔드를 재사용
- AI는 전체 파이프라인을 대체하기보다 처음과 마지막을 가볍게 점검하는 방향

## 현재 구현

### 배포/실행 형태

현재 구현된 실행 표면은 3개다.

1. 데스크톱 앱
   Tauri가 release 환경에서 Python backend sidecar를 자동 시작하고, 실행 시 사용 가능한 로컬 포트를 자동 선택한다.
2. 웹 UI
   Next.js 정적 결과물을 FastAPI가 서빙한다.
3. CLI
   GUI 없는 서버에서도 `serve`, `run`, `repl`, `tools` 모드로 같은 백엔드를 사용할 수 있다.

### 현재 레이어 구조

```text
Client (Web / Mobile WebView / CLI)
    ->
Gateway (FastAPI, auth, local-only route guard, static serving)
    ->
Intent Router (rules first, AI fallback only when needed)
    ->
AI review layer (처음/마지막 점검, AI continuation)
    ->
Orchestrator (task status, approval-required state, sequential tool execution)
    ->
Tools (file / shell / crawler / time / system_info)
    ->
Local resources (SQLite / filesystem / cloudflared / external HTTP)
```

### 현재 요청 처리 흐름

#### 일반 명령

```text
사용자 요청
  -> Intent Router
  -> 규칙 매칭 성공 시 바로 Step 생성
  -> 필요 시 AI가 첫 Step을 가볍게 점검
  -> Orchestrator
  -> Tool 실행
  -> 필요 시 AI가 마지막 결과를 가볍게 점검
  -> 결과 저장 및 요약
```

#### AI 폴백 명령

```text
사용자 요청
  -> 규칙 매칭 실패
  -> AI agent가 실행 계획 생성
  -> Orchestrator
  -> Tool 실행
  -> 결과 저장 및 요약
```

#### 마지막 결과가 약할 때 AI takeover

```text
사용자 요청
  -> 비AI Step 먼저 실행
  -> AI가 마지막 결과가 부족하다고 판단
  -> AI continuation이 다음 Step 생성
  -> Orchestrator가 이어서 실행
```

#### 승인 필요 명령

```text
사용자 요청
  -> Intent Router에서 위험도 계산
  -> medium/high 이면 approval_required 상태 저장
  -> 사용자가 승인 API 호출
  -> Orchestrator가 기존 계획 재실행
```

#### 스케줄 실행

```text
Schedule 등록
  -> APScheduler가 cron 기준으로 실행
  -> Intent Router
  -> Orchestrator
  -> Tool 실행
```

## 현재 인증/원격 접속 구조

### 로컬 요청

- `127.0.0.1`, `localhost` 요청은 인증 없이 허용
- 대신 로컬 전용 엔드포인트는 원격 접근이 차단됨

### 원격 요청

- Cloudflare Tunnel을 통해 로컬 백엔드에 접근
- 원격 방식은 Quick Tunnel 또는 정식 Cloudflare Tunnel 중 하나
- 패키징된 데스크톱 앱은 `cloudflared`를 함께 제공하는 방향
- 소스 기반 환경에서는 여전히 호스트 머신의 `cloudflared`가 필요
- 페어링 토큰 기반 인증 사용
- 원격 첫 진입은 `?_token=`으로 부트스트랩 가능
- 이후는 인증 쿠키 또는 Bearer 토큰 사용

### 페어링 흐름

```text
PC 로컬 UI
  -> 터널 URL + 토큰 확인
  -> 모바일 앱이 QR 또는 수동 입력으로 저장
  -> 모바일 WebView가 원격 UI 로드
```

## 현재 주요 구성요소

### Gateway

- HTTP 요청 수신
- 인증 및 로컬 전용 경로 보호
- `/command`, `/task`, `/approvals`, `/schedules`, `/pair`, `/setup`, `/widget` 제공

### Intent Router

- YAML 규칙 기반 명령 매칭
- 규칙 실패 시 AI 호출
- Step별 위험도 계산

### Orchestrator

- 순차 실행
- 상태 저장
- 승인 필요 상태 저장
- 승인 후 재실행
- 마지막 결과에 대한 AI 점검
- 필요 시 AI continuation으로 자연스럽게 handoff
- 결과 요약

### Tools

- `file`
- `shell`
- `crawler`
- `time`
- `system_info`

참고:

- 낮은 수준의 Tool 종류는 적어도, 플러그인이 캘린더, 커뮤니케이션, 길찾기, 리마인더, 날씨, 쇼핑 같은 요청을 이미 꽤 많이 덮고 있다

### Scheduler

- APScheduler 기반 cron 실행

### Tunnel

- `cloudflared` 시작/종료
- 터널 URL 추출
- 페어링 토큰 생성/검증/회전

## 보안 원칙

- 로컬 전용 엔드포인트와 원격 엔드포인트를 분리
- 원격 요청은 토큰 인증 필요
- 셸 실행은 allowlist + argv 기반 실행
- 파일 접근은 허용 디렉터리 기반 제한
- 내부 민감 파일 접근 차단
- 위험도 `medium/high` 작업은 승인 필요

## 향후 확장

아래는 방향성은 있지만 아직 현재 코드에 완전히 구현되지 않은 항목이다.

### 실시간 업데이트

- WebSocket 기반 Task 상태/로그 스트리밍

### 더 정교한 오케스트레이션

- Task Graph
- 병렬 실행
- 조건 분기
- 재시도 정책 고도화

### 추가 Tool

- `calendar`
- `message`
- 설치/패키지 관리 관련 Tool

### 사용자 경험 확장

- 모바일 위젯 실제 구현
- 더 풍부한 승인/스케줄 UI
- 오픈소스 배포용 README 및 운영 가이드 강화

### 인증 고도화

- 토큰 관리 개선
- 더 확장 가능한 세션/사용자 모델

## 기술 스택

| 영역 | 기술 |
|------|------|
| 데스크톱 런타임 | Tauri 2 |
| Backend | Python / FastAPI / uvicorn |
| Scheduler | APScheduler |
| DB | SQLite |
| Frontend | Next.js 15 / TypeScript |
| Mobile | React Native + WebView |
| 터널 | Cloudflare Tunnel (`cloudflared`) |
| AI | Anthropic API, 필요 시에만 사용 |

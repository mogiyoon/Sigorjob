# API Spec

## 기본 정보

- Base URL: `http://127.0.0.1:8000`
- 요청/응답: JSON
- 현재 구현은 REST 중심이며 WebSocket은 아직 없음

## 인증 모델

- 로컬 루프백 요청(`127.0.0.1`, `localhost`)은 인증 없이 접근 가능
- 원격 요청은 페어링 토큰이 필요
- 원격 첫 진입은 `?_token=`으로 부트스트랩 가능
- 원격 이후 요청은 `Authorization: Bearer <token>` 또는 서버가 설정한 인증 쿠키로 처리

## 로컬 전용 엔드포인트

아래 경로는 로컬에서만 접근 가능하며, 원격 요청 시 `403 forbidden`이 반환된다.

- `GET /pair/data`
- `GET /pair/status`
- `POST /pair/rotate`
- `GET /setup/status`
- `POST /setup/quick`
- `POST /setup/cloudflare`
- `DELETE /setup/cloudflare`
- `/docs`
- `/openapi.json`

## Endpoints

### POST /command

사용자 명령을 받아 Task를 생성하고 비동기로 실행한다.

### GET /task/{task_id}

Task 상태와 결과를 조회한다.

주요 상태 값:

- `pending`
- `running`
- `done`
- `failed`
- `approval_required`
- `cancelled`

### GET /tools

현재 등록된 Tool 목록을 반환한다.

현재 기본 Tool:

- `file`
- `shell`
- `crawler`
- `time`
- `system_info`

### GET /approvals

승인 대기 중인 작업 목록을 반환한다.

### POST /approval/{task_id}

승인 대기 중인 작업을 승인하거나 거부한다.

### POST /schedule

cron 형식으로 반복 실행할 작업을 등록한다.

### GET /schedules

등록된 스케줄 목록을 반환한다.

### DELETE /schedule/{schedule_id}

등록된 스케줄을 삭제한다.

### GET /widget/summary

모바일 위젯이나 간단한 대시보드에서 재사용할 수 있는 요약 데이터를 반환한다.

### GET /pair/data

모바일 연결용 터널 URL과 페어링 토큰을 반환한다. 로컬 전용 엔드포인트다.

### GET /pair/status

터널 연결 상태를 반환한다. 로컬 전용 엔드포인트다.

### POST /pair/rotate

기존 페어링 토큰을 폐기하고 새 토큰을 생성한다. 로컬 전용 엔드포인트다.

### GET /setup/status

원격 터널 설정 여부, 선택된 터널 방식, 현재 터널 상태를 반환한다. 로컬 전용 엔드포인트다.

### POST /setup/quick

Quick Tunnel 모드를 시작하고 임시 `trycloudflare.com` URL을 발급받으려 시도한다. 로컬 전용 엔드포인트다.

### POST /setup/cloudflare

Cloudflare 정식 터널 토큰을 저장하고 터널 연결을 시도한다. 로컬 전용 엔드포인트다.

### DELETE /setup/cloudflare

저장된 Cloudflare 터널 토큰을 삭제하고 현재 터널을 종료한다. 로컬 전용 엔드포인트다.

### GET /tasks

현재 기계의 최근 작업 목록을 반환한다.

## 현재 미구현 항목

- WebSocket 기반 실시간 업데이트
- JWT 인증

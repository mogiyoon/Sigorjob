# Debug Regressions

이 문서는 반복해서 되돌아가거나 다시 깨졌던 런타임 이슈를 정리한 메모다.

목적:

- 같은 버그를 다시 만들지 않기
- 런타임 관련 코드를 건드릴 때 먼저 확인할 기준 만들기
- "고쳤던 것 같은데 또 안 됨" 상황을 줄이기

이 문서를 먼저 봐야 하는 작업:

- Tauri startup / shutdown
- backend sidecar 실행 방식
- `cloudflared` / 모바일 간편 연결
- 로컬 API 포트
- 패키징 순서
- 웹에서는 되는데 Tauri에서 안 되는 UI

## 반드시 확인할 것

1. 포트 가정이 하드코딩돼 있지 않은지 확인
2. startup에서 sidecar를 죽이거나 readiness를 잘못 판단하지 않는지 확인
3. 종료 시 `backend`와 `cloudflared`가 실제로 내려가는지 확인
4. 패키징 결과물에 정적 파일과 기본 플러그인이 포함되는지 확인
5. 웹 전용 API를 Tauri에서도 그대로 쓰고 있지 않은지 확인

## 반복된 회귀

### 1. 동적 포트라고 했지만 실제 코드는 8000 고정

현재 코드 기준으로 다음 위치가 여전히 `8000`을 직접 가정한다.

- [src-tauri/src/main.rs](/Users/nohgiyoon/Coding/AI/Agent/src-tauri/src/main.rs)
- [backend/tunnel/manager.py](/Users/nohgiyoon/Coding/AI/Agent/backend/tunnel/manager.py)
- [frontend/src/lib/api.ts](/Users/nohgiyoon/Coding/AI/Agent/frontend/src/lib/api.ts)
- [backend/cli.py](/Users/nohgiyoon/Coding/AI/Agent/backend/cli.py)

의미:

- "동적 포트 적용됨"이라고 말하기 전에 실제 코드에서 포트 공유가 끝까지 연결되어 있는지 확인해야 한다.
- startup probe, frontend base URL, tunnel target이 같은 포트를 보고 있어야 한다.

### 2. Tauri startup이 초기 커밋보다 너무 복잡해짐

초기 커밋 `b62d24cb`의 [src-tauri/src/main.rs](/Users/nohgiyoon/Coding/AI/Agent/src-tauri/src/main.rs)는 사실상 `backend` sidecar를 바로 `spawn()`만 했다.

지금은 여기에 아래가 추가되어 있다.

- 앱 락
- 기존 프로세스 정리
- startup 로그 수집
- readiness 대기
- 종료 시 cleanup

의미:

- startup 문제가 생기면 "터널 문제"보다 먼저 Tauri startup 경로를 의심한다.
- 무언가 안 뜰 때는 먼저 `backend`가 실제로 살아 있는지 포트와 프로세스를 확인한다.

### 3. 준비 대기 실패가 앱 전체 실패처럼 보일 수 있음

패턴:

- 오래 켜둔 앱을 끄고 다시 켜면 readiness가 실패
- 실제로는 이전 `backend`나 `cloudflared`가 늦게 내려가거나 startup cleanup과 race가 남

의미:

- startup에서 단순 timeout만 보지 말고 "이전 세션 정리 완료 여부"를 같이 확인해야 한다.
- 재현되면 먼저 `lsof`와 `pgrep`로 잔존 프로세스를 확인한다.

### 4. 모바일 간편 연결은 터널보다 먼저 backend 생존 여부를 봐야 함

반복 패턴:

- 모바일 연결이 안 된다고 느껴지지만 실제로는 `backend`가 안 뜨거나 `/pair`가 404였음
- `cloudflared`보다 먼저 local backend health를 확인해야 했다

의미:

- 확인 순서는 항상 `backend -> /setup/status -> /pair -> tunnel` 이다.

### 5. 패키징 순서가 잘못되면 `/pair`, `/setup`가 404

반복 패턴:

- frontend 정적 파일이 backend bundle에 포함되지 않아 모바일 연결 페이지가 404

의미:

- 앱 패키징은 `frontend -> backend -> tauri` 순서를 유지해야 한다.

### 6. 기본 플러그인 누락으로 `tool not found`

반복 패턴:

- 소스 실행에서는 되는데 패키징 앱에서 `calendar_helper` 같은 기본 플러그인이 사라짐

의미:

- backend 패키징에 `backend/plugins` 전체 포함 여부를 항상 확인한다.

### 7. 웹에서는 되는데 Tauri에서는 안 되는 UI

이미 한 번 이상 문제된 항목:

- `window.confirm`
- `<a target="_blank">`
- `navigator.clipboard`
- 런타임을 브라우저처럼 가정하는 `window.location` 분기

의미:

- 새 UI를 만들 때는 "브라우저에서 됨"으로 끝내지 말고 Tauri-safe 경로가 있는지 확인한다.

### 8. 실행 결과가 사라져 보이는 UI

반복 패턴:

- 완료 직후 task가 다른 섹션으로 이동해서 유실처럼 보임
- 실패 메시지가 콘솔에만 있고 화면엔 안 보임

의미:

- 작업 상태 전환 시 사용자 눈앞에서 사라지지 않는지 확인한다.
- 실패는 화면에도 반드시 보여줘야 한다.

## 런타임 점검 순서

문제가 생기면 이 순서로 본다.

1. `lsof -nP -iTCP -sTCP:LISTEN`으로 `backend`, `cloudflared`, `8000` 확인
2. 앱이 최신 번들인지 확인
3. `/setup/status` 응답 확인
4. `/pair`와 `/setup`가 404가 아닌지 확인
5. 남아 있는 sidecar가 있는지 확인
6. 그 다음에야 터널과 모바일 앱을 본다

## 구현 전 체크리스트

런타임 관련 코드를 바꾸기 전에 아래를 확인한다.

- 이 변경이 startup을 더 복잡하게 만드는가
- 기존 프로세스 정리와 race를 만들지 않는가
- 포트 가정이 하드코딩되어 있지 않은가
- 패키징된 앱 기준으로도 동작하는가
- 웹 전용 동작을 Tauri에 그대로 가져오지 않았는가
- "예전엔 됐는데 다시 안 됨" 케이스를 이 문서에 추가했는가


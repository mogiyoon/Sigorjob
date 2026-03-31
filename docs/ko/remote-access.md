# Remote Access

## Overview

원격 접속은 선택 기능입니다.
로컬 데스크톱, 로컬 웹, CLI 사용은 원격 기능 없이도 가능합니다.

원격 웹 접속과 모바일 페어링에는 아래가 필요합니다.

- 실행 중인 로컬 백엔드
- 런타임에서 사용할 수 있는 `cloudflared`
- Quick Tunnel 또는 설정된 Cloudflare 터널 토큰

패키징된 데스크톱 앱 기준으로는:

- 백엔드 sidecar가 실행 시 빈 로컬 포트를 자동 선택합니다.
- 터널도 그 런타임 포트를 따라가며, 더 이상 `127.0.0.1:8000` 고정 전제를 두지 않습니다.

정상적인 제품 방향은 이렇습니다.

- 패키징된 데스크톱 앱은 최종 사용자에게 `cloudflared`를 함께 제공합니다.
- 소스 기반 개발이나 로컬 패키징 환경에서는 호스트에 설치된 `cloudflared` 또는 `CLOUDFLARED_PATH`를 사용할 수 있습니다.

## `cloudflared` 설치

패키징된 데스크톱 앱 기준으로는 최종 사용자가 `cloudflared`를 따로 설치하지 않는 방향을 목표로 합니다.

아래 설치 방법은 주로 개발자, 소스 실행 환경, 패키징 머신을 위한 안내입니다.

### macOS

권장 방법:

```bash
brew install cloudflared
```

대안:

- Cloudflare 공식 다운로드 페이지에서 macOS 바이너리를 직접 받습니다.
- 일반 `PATH` 밖에 설치했다면 `CLOUDFLARED_PATH`를 직접 설정합니다.

### Windows

권장 방법:

- Cloudflare 공식 다운로드 페이지에서 `cloudflared.exe`를 직접 받습니다.

대안:

```powershell
winget install Cloudflare.cloudflared
```

실행 파일이 `PATH`에 없다면 `CLOUDFLARED_PATH`로 경로를 지정합니다.

### 설치 확인

설치 후에는 아래처럼 확인합니다.

```bash
cloudflared --version
```

이 명령이 동작하지 않으면 실행 파일의 전체 경로를 `CLOUDFLARED_PATH`로 설정해야 합니다.

## Readiness Check

원격 기능까지 포함한 배포 준비 상태 확인:

```bash
./scripts/check-dist-readiness.sh --with-remote
```

백엔드 실행 후 실제 원격 준비 상태 확인:

```bash
./scripts/check-remote-flow.sh
```

다른 로컬 주소를 직접 넘길 수도 있습니다.

```bash
./scripts/check-remote-flow.sh http://127.0.0.1:8000
```

## Local Setup Flow

1. 백엔드나 데스크톱 앱을 실행합니다.
2. 로컬 setup 페이지를 엽니다.
3. `cloudflared` 사용 가능 여부를 확인합니다.
4. 원격 방식 하나를 고릅니다.
   - Quick Tunnel: 토큰 없이 바로 시작
   - 정식 Tunnel: Cloudflare Zero Trust의 터널 토큰 입력
5. 터널 URL이 나타날 때까지 기다립니다.
6. 로컬 pairing 페이지를 엽니다.
7. 페어링 토큰을 복사하거나 모바일 앱 연결을 완료합니다.
8. Quick Tunnel을 다시 열었다면 새 QR을 다시 스캔해야 합니다. 임시 주소가 바뀔 수 있기 때문입니다.

## 원격 방식

### Quick Tunnel

- Cloudflare 계정이나 토큰이 없어도 됩니다.
- 앱이 `cloudflared`를 통해 임시 `trycloudflare.com` 주소를 받습니다.
- 테스트나 빠른 원격 연결에 가장 적합합니다.
- 다만 다시 시작하면 주소가 바뀔 수 있어 장기적으로 고정 주소가 필요한 경우에는 적합하지 않을 수 있습니다.

### 정식 Tunnel

- Cloudflare Zero Trust에서 발급한 터널 토큰이 필요합니다.
- Cloudflare 쪽에서 public hostname 또는 route 설정도 필요합니다.
- 장기적으로 더 안정적인 원격 주소가 필요할 때 적합합니다.
- 대신 Quick Tunnel보다 설정 단계가 더 많습니다.

## Common States

### `cloudflared` missing

- 아직 원격 접속을 사용할 수 없습니다.
- 패키징된 앱이라면 번들이 불완전할 가능성이 있습니다.
- 소스 실행 환경이라면 `cloudflared`를 설치하거나 `CLOUDFLARED_PATH`를 설정해야 합니다.

### 정식 터널 토큰이 설정되지 않음

- 로컬 사용은 계속 가능합니다.
- Quick Tunnel은 계속 사용할 수 있습니다.
- 정식 Tunnel 기반 원격/모바일 접속은 터널 토큰을 저장하기 전까지 사용할 수 없습니다.

### Tunnel configured but inactive

- Quick Tunnel을 쓰는 중이라면 다시 시도하고 로컬 네트워크 상태를 확인합니다.
- 정식 Tunnel을 쓰는 중이라면 토큰이 올바른지 다시 확인합니다.
- 정식 Tunnel은 Cloudflare의 public hostname 또는 route도 다시 확인합니다.
- 로컬 네트워크 상태를 확인합니다.
- setup 페이지를 다시 열어 표시되는 터널 에러를 확인합니다.

### Pairing ready

- 로컬 머신에 터널 URL이 생성된 상태입니다.
- 모바일 앱이 페어링 토큰으로 연결할 수 있습니다.

### 모바일 공유 텍스트

- Android는 다른 앱에서 공유한 텍스트를 Sigorjob으로 받아 바로 데스크톱 백엔드 `/command`로 보낼 수 있습니다.
- iOS도 Share Extension + 앱 handoff 방식으로 같은 흐름을 맞추는 중입니다.
- 이 기능 역시 현재 터널 주소와 PC 호스트가 정상이어야 동작합니다.

## Security Notes

- setup 과 pairing API는 로컬 전용입니다.
- 원격 요청은 페어링 토큰이 필요합니다.
- 최초 원격 로드는 `?_token=`으로 bootstrap 될 수 있습니다.
- 이후에는 auth cookie 또는 bearer token으로 유지됩니다.

## Official References

- Cloudflare 다운로드: https://developers.cloudflare.com/tunnel/downloads/
- Cloudflare 터널 토큰 실행: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/configure-tunnels/cloudflared-parameters/run-parameters/

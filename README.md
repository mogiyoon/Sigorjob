<p align="center">
  <img src="./sigorjob.png" alt="Sigorjob" width="160" />
</p>

<p align="center">
  <strong>Automation for everyone. AI only when needed.</strong>
</p>

# Sigorjob

Sigorjob is a local-first automation system that uses the user's PC as the execution hub.
It is designed to behave like a general-purpose AI agent, while minimizing actual AI usage wherever rules-based automation, plugins, or user customization can handle the work.

## Core Idea

- The local PC is the execution authority
- Web, mobile, and CLI are control surfaces
- Rules-based automation is the default first path
- If non-AI logic misses, AI should still be able to take over and continue the request
- Low AI usage is a product differentiator, not just a cost optimization
- Over time, successful AI flows should be absorbed into non-AI plugins and automations
- External services should be handled through one shared connection model instead of one-off popups or feature-specific flows

## Current Status

The project is currently in a working MVP stage.

Local-only usage is the easiest path today:

- local desktop and local web usage can work without Cloudflare Tunnel
- CLI usage on the same machine does not require `cloudflared`
- packaged desktop builds bundle `cloudflared` for remote/mobile usage
- source-based remote/mobile usage still requires a local `cloudflared` install or `CLOUDFLARED_PATH`
- source-based execution still requires normal development dependencies
- remote access can use either:
  - Quick Tunnel for the fastest setup and a temporary URL
  - a named Cloudflare tunnel for a more stable long-term URL

Implemented today:

- FastAPI backend
- rules-first intent routing with AI fallback
- lightweight AI checks at the beginning and end of the pipeline
- sequential orchestrator
- approval-required task flow
- recurring schedules with APScheduler
- tools: `file`, `shell`, `crawler`, `time`, `system_info`
- Next.js web UI
- React Native mobile WebView wrapper
- Android share-to-app flow for shared text commands
- iOS share-extension groundwork for shared text commands
- Tauri desktop shell
- packaged desktop runtime that auto-picks an available local backend port
- headless CLI mode
- Cloudflare Tunnel based remote access
- shared connection registry groundwork for mobile, AI, Gmail, Calendar, and future MCP tools

Still planned:

- WebSocket real-time updates
- more advanced orchestration
- more native external-service completion beyond helper/open-page flows
- production-grade mobile widget support

## Project Structure

- [Documentation index](./docs/README.md)
- [English architecture](./docs/en/architecture.md)
- [English API spec](./docs/en/api-spec.md)
- [English modules](./docs/en/modules.md)
- [English remote access guide](./docs/en/remote-access.md)
- [English cautions](./docs/en/cautions.md)

## Running the Project

### Local vs remote requirements

- Local desktop, local web, and CLI usage can work without Cloudflare Tunnel.
- Packaged desktop builds bundle `cloudflared` for remote web access and mobile pairing.
- Source-based remote usage still requires `cloudflared` on the build machine.
- If you only want local automation on the same machine, you can skip tunnel setup.
- Remote setup supports both Quick Tunnel and token-based named tunnels.

### Backend server

```bash
cd backend
python main.py serve
```

### CLI mode

```bash
./scripts/cli.sh run "pwd"
./scripts/cli.sh repl
./scripts/cli.sh tools
```

### Development mode

```bash
./scripts/dev.sh
```

### Mobile app builds

Android release APK:

```bash
cd mobile/android
./gradlew assembleRelease
```

The generated APK is written to:

- `mobile/android/app/build/outputs/apk/release/app-release.apk`

iOS workspace setup:

```bash
cd mobile/ios
pod install
```

Then open:

- `mobile/ios/Sigorjob.xcworkspace`

Recommended iOS flow:

- open the workspace in Xcode
- select your Apple signing team
- keep the app display name as `Sigorjob`
- run on a simulator or connected iPhone

Notes for iOS:

- camera permission is required for QR pairing
- the current mobile experience is centered on QR/manual pairing plus the WebView shell
- Android currently has the more complete local-notification path
- iOS share-to-app support now uses a Share Extension plus app URL handoff
- local Xcode/Simulator health still matters for validating the iOS extension end to end

### Backend tests

```bash
./scripts/test-backend.sh
```

### Distribution readiness check

```bash
./scripts/check-dist-readiness.sh
```

To also verify remote/mobile prerequisites:

```bash
./scripts/check-dist-readiness.sh --with-remote
```

### Remote access runtime check

```bash
./scripts/check-remote-flow.sh
```

Remote setup modes:

- Quick Tunnel
  - no token required
  - easiest onboarding path
  - temporary URL that may change after restart
- Named Cloudflare Tunnel
  - requires a Cloudflare tunnel token
  - requires a public hostname or route configured in Cloudflare
  - better for stable long-term remote URLs

### `cloudflared` installation

- End users of packaged desktop builds should not need to install it separately.
- Developers building the desktop app can install it locally so the build can bundle it.
- macOS build machines: `brew install cloudflared`
- Windows build machines: install the official `cloudflared.exe` or use `winget install Cloudflare.cloudflared`
- If needed during source-based development or packaging, set `CLOUDFLARED_PATH` to the installed binary location

### Desktop distributable build

```bash
./scripts/build-app.sh
```

To additionally produce a macOS DMG:

```bash
./scripts/build-app.sh --with-dmg
```

Before using remote tunnel features in source-based environments, make sure `cloudflared` is installed on the host machine or exposed via `CLOUDFLARED_PATH`.

## Git Workflow

- Create short-lived feature branches from `dev`
- Open pull requests from `feature -> dev`
- Promote tested changes with pull requests from `dev -> main`
- Merge manually after review and verification
- Do not use `rebase merge` or `squash merge` in the normal project workflow

## Security Notes

- Local-only setup and pairing routes are blocked from remote access
- Remote access uses pairing-token-based authentication
- Shell execution is allowlisted and argv-based
- File access is restricted to allowed directories
- Medium and high risk tasks require approval

## Packaging Notes

- Source execution still requires local development dependencies such as Python packages and Node modules.
- The intended no-extra-installation experience comes from packaged artifacts:
  - Python backend bundled as a single binary with PyInstaller
  - desktop app bundled with Tauri
- packaged desktop builds now auto-select an available local API port instead of assuming `127.0.0.1:8000`
- packaged desktop builds also bundle `cloudflared` for remote/mobile access.
- Source checkouts and development builds may still rely on a local `cloudflared` install or `CLOUDFLARED_PATH`.
- `./scripts/check-dist-readiness.sh` validates local build prerequisites.
- `./scripts/check-dist-readiness.sh --with-remote` validates that the build machine can bundle `cloudflared`.
- `./scripts/build-app.sh` builds the app bundle by default.
- `./scripts/build-app.sh --with-dmg` also attempts DMG packaging, which can be more environment-sensitive on macOS.
- The project now includes a distribution readiness check, but cross-machine packaging validation is still an important release step.

## Dependency Notes

- `cloudflared` is optional for local-only usage.
- Packaged desktop builds are intended to include `cloudflared` for end users.
- Source-based remote/mobile usage still requires `cloudflared` on the local machine.
- `slowapi` enables rate limiting, but the backend now runs without it and logs a warning instead of failing at import time.
- Core Python dependencies live in [backend/requirements.txt](/Users/nohgiyoon/Coding/AI/Agent/backend/requirements.txt).
- Optional Python dependencies live in [backend/requirements-optional.txt](/Users/nohgiyoon/Coding/AI/Agent/backend/requirements-optional.txt).

## Documentation Languages

This repository keeps docs in both English and Korean.

- English docs live under `docs/en`
- Korean docs live under `docs/ko`
- Root files under `docs/` are English guidance pages

## 한국어 요약

Sigorjob은 사용자의 PC를 실행 허브로 사용하는 로컬 우선 자동화 시스템입니다.
겉으로는 범용 AI 비서처럼 느껴지지만, 실제로는 가능한 한 규칙 기반 자동화로 먼저 처리하고 꼭 필요한 순간에만 AI를 사용하도록 설계되어 있습니다.

핵심 포인트:

- 로컬 PC가 실제 실행 권한을 가집니다
- 웹, 모바일, CLI는 제어 화면 역할을 합니다
- 기본 경로는 비AI 자동화입니다
- 비AI가 놓치면 AI가 이어서 처리합니다
- 낮은 AI 사용량 자체가 제품 차별점입니다
- Gmail, Calendar, MCP 같은 외부 기능은 공통 연결 모델로 확장하는 방향입니다

현재 구현 상태:

- FastAPI 백엔드
- 규칙 우선 intent routing + AI fallback
- 시작/마지막 단계의 얇은 AI 점검
- 순차 오케스트레이터
- 승인 기반 작업 흐름
- 반복 스케줄
- 웹 UI, 모바일 앱, Tauri 데스크톱 앱, CLI
- Android 공유 버튼으로 들어온 텍스트 실행
- Cloudflare Tunnel 기반 원격 접속

빠른 시작:

```bash
./scripts/dev.sh
```

백엔드만 실행:

```bash
cd backend
python main.py serve
```

CLI 사용:

```bash
./scripts/cli.sh run "pwd"
./scripts/cli.sh repl
```

문서:

- 한국어 문서: `docs/ko`
- 영어 문서: `docs/en`
- 문서 인덱스: [docs/README.md](./docs/README.md)

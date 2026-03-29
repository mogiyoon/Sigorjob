# API Spec

## Basics

- Base URL: `http://127.0.0.1:8000`
- Request/response format: JSON
- The current implementation is REST-first. WebSocket is not implemented yet.

## Authentication Model

- Local loopback requests (`127.0.0.1`, `localhost`) are allowed without authentication.
- Remote requests require a pairing token.
- The first remote load can bootstrap with `?_token=`.
- Subsequent remote requests use either `Authorization: Bearer <token>` or the auth cookie set by the server.

## Local-Only Endpoints

The following routes are only accessible locally and return `403 forbidden` for remote access:

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

Creates a task from a user command and runs it asynchronously.

### GET /task/{task_id}

Returns task status and result.

Main status values:

- `pending`
- `running`
- `done`
- `failed`
- `approval_required`
- `cancelled`

### GET /tools

Returns the currently registered tools.

Current default tools:

- `file`
- `shell`
- `crawler`
- `time`
- `system_info`

### GET /approvals

Returns tasks waiting for approval.

### POST /approval/{task_id}

Approves or rejects a task in the approval queue.

### POST /schedule

Registers a recurring job using cron syntax.

### GET /schedules

Returns the registered schedules.

### DELETE /schedule/{schedule_id}

Deletes a schedule.

### GET /widget/summary

Returns lightweight summary data intended for a mobile widget or compact dashboard surface.

### GET /pair/data

Returns the tunnel URL and pairing token used for mobile pairing. Local-only endpoint.

### GET /pair/status

Returns the current tunnel state. Local-only endpoint.

### POST /pair/rotate

Rotates the current pairing token and invalidates the previous one. Local-only endpoint.

### GET /setup/status

Returns remote-tunnel setup status, selected tunnel mode, and current tunnel state. Local-only endpoint.

### POST /setup/quick

Starts Quick Tunnel mode and attempts to get a temporary `trycloudflare.com` URL. Local-only endpoint.

### POST /setup/cloudflare

Stores the Cloudflare named-tunnel token and attempts to start the tunnel. Local-only endpoint.

### DELETE /setup/cloudflare

Deletes the stored Cloudflare tunnel token and stops the current tunnel. Local-only endpoint.

### GET /tasks

Returns recent tasks for the current machine.

## Not Yet Implemented

- WebSocket-based real-time updates
- JWT authentication

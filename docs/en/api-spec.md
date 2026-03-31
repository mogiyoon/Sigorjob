# API Spec

## Basics

- Local source default Base URL: `http://127.0.0.1:8000`
- Packaged desktop builds now choose an available local port at runtime
- Request/response format: JSON
- The current implementation is REST-first. WebSocket is not implemented yet.

## Authentication Model

- Local loopback requests (`127.0.0.1`, `localhost`) are allowed without authentication.
- Remote requests require a pairing token.
- The first remote load can bootstrap with `?_token=`.
- Subsequent remote requests use either `Authorization: Bearer <token>` or the auth cookie set by the server.

## Local-Only Endpoints

The following routes are only accessible locally and return `403 forbidden` for remote access:

- `GET /pair`
- `GET /pair/data`
- `GET /pair/status`
- `POST /pair/rotate`
- `GET /setup`
- `GET /setup/status`
- `GET /setup/connections`
- `POST /setup/connections/{connection_id}`
- `POST /setup/permissions`
- `POST /setup/ai`
- `POST /setup/ai/verify`
- `DELETE /setup/ai`
- `POST /setup/quick`
- `POST /setup/cloudflare`
- `DELETE /setup/cloudflare`
- `DELETE /setup/tunnel`
- `POST /mobile/notifications/test`
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

### POST /task/{task_id}/retry

Creates a new retry task from the original command.

### POST /task/{task_id}/continue-ai

Asks AI to continue or refine an existing result.
This may either:

- refine an existing draft such as email/message content
- append more result items from AI-generated continuation steps

### DELETE /task/{task_id}

Deletes one task and its logs/approval records.

### POST /tasks/delete

Deletes multiple tasks at once.

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

### GET /setup/connections

Returns the shared connection registry items shown in setup UI. Local-only endpoint.

### POST /setup/connections/{connection_id}

Updates a non-core external connection entry. Local-only endpoint.

### POST /setup/permissions

Updates a stored permission toggle. Local-only endpoint.

### POST /setup/ai

Stores the AI API key and performs validation. Local-only endpoint.

### POST /setup/ai/verify

Re-validates AI connectivity using the stored key. Local-only endpoint.

### DELETE /setup/ai

Removes the stored AI key. Local-only endpoint.

### POST /setup/quick

Starts Quick Tunnel mode and attempts to get a temporary `trycloudflare.com` URL. Local-only endpoint.

### POST /setup/cloudflare

Stores the Cloudflare named-tunnel token and attempts to start the tunnel. Local-only endpoint.

### DELETE /setup/cloudflare

Deletes the stored Cloudflare tunnel token and stops the current tunnel. Local-only endpoint.

### DELETE /setup/tunnel

Stops the current tunnel regardless of mode. Local-only endpoint.

### GET /tasks

Returns recent tasks for the current machine.

### GET /mobile/notifications

Returns queued mobile notifications for a paired mobile client.

### POST /mobile/notifications/ack

Marks mobile notifications as acknowledged.

### POST /mobile/notifications/test

Queues a test mobile notification. Local-only endpoint.

## Not Yet Implemented

- WebSocket-based real-time updates
- JWT authentication

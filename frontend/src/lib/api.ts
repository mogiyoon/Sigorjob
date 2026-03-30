/**
 * API 클라이언트
 *
 * - PC (Tauri/브라우저): http://127.0.0.1:8000 으로 직접 호출
 * - 모바일 WebView: 터널 URL을 통해 로드되므로 상대 경로 사용
 *   (window.location.origin == 터널 URL → same-origin)
 *
 * 토큰:
 * - 모바일 앱이 ?_token= 쿼리로 최초 진입
 * - 백엔드가 검증 후 HttpOnly 쿠키를 설정
 * - 프론트는 URL에서 토큰을 제거만 하고 저장하지 않음
 */

export function getBaseUrl(): string {
  if (typeof window === "undefined") return "http://127.0.0.1:8000";
  const origin = window.location.origin;
  // 로컬 개발 환경
  if (origin.includes("localhost") || origin.includes("127.0.0.1")) {
    return process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
  }
  // 터널 URL에서 로드된 경우 — 같은 오리진으로 API 호출
  return origin;
}

export function getLocalApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
}

export function clearToken() {
  // 인증 쿠키는 HttpOnly로 관리되므로 클라이언트에서 직접 삭제하지 않는다.
}

export class UnauthorizedError extends Error {
  constructor(message = "unauthorized") {
    super(message);
    this.name = "UnauthorizedError";
  }
}

/** URL에 _token 쿼리가 있으면 저장하고 URL에서 제거 */
export function initTokenFromUrl() {
  if (typeof window === "undefined") return;
  const params = new URLSearchParams(window.location.search);
  const token = params.get("_token");
  if (token) {
    params.delete("_token");
    const newUrl = window.location.pathname + (params.toString() ? `?${params}` : "");
    window.history.replaceState({}, "", newUrl);
  }
}

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  const res = await fetch(`${getBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (res.status === 401) {
    throw new UnauthorizedError("토큰이 만료되었거나 유효하지 않습니다.");
  }
  return res;
}

export async function localApiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${getLocalApiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
}

export interface TaskResponse {
  task_id: string;
  command?: string | null;
  status: "pending" | "running" | "done" | "failed" | "approval_required" | "cancelled";
  result: { summary: string; results: unknown[] } | null;
  created_at?: string | null;
  completed_at?: string | null;
}

export interface ApprovalItem {
  task_id: string;
  command: string;
  risk_level: string;
  reason: string | null;
  created_at: string;
}

export interface ScheduleItem {
  schedule_id: string;
  name: string;
  command: string;
  cron: string;
  status: string;
  created_at: string;
  last_run_at: string | null;
  next_run_at: string | null;
}

export interface PermissionItem {
  id: string;
  title: string;
  description: string;
  source: string;
  required_for: string[];
  granted: boolean;
  risk?: "low" | "medium" | "high";
}

export interface ConnectionItem {
  id: string;
  title: string;
  description: string;
  provider: string;
  kind: "core" | "external";
  connection_type: string;
  required_permissions: string[];
  configured: boolean;
  verified: boolean;
  available: boolean;
  account_label: string | null;
  metadata: Record<string, unknown>;
  status:
    | "connected"
    | "configured"
    | "not_connected"
    | "missing_dependency"
    | "available"
    | "planned";
  next_action: string;
}

export interface SetupStatusResponse {
  configured: boolean;
  tunnel_mode: "none" | "quick" | "cloudflare";
  tunnel_active: boolean;
  tunnel_url: string | null;
  cloudflared_installed: boolean;
  cloudflared_path: string | null;
  tunnel_error: string | null;
  ai_configured: boolean;
  ai_verified: boolean;
  ai_validation_error: string | null;
  ai_verified_at: string | null;
  ai_storage_backend: "keychain" | "config";
  connections: ConnectionItem[];
  permissions: PermissionItem[];
}

export async function sendCommand(text: string): Promise<TaskResponse> {
  const res = await apiFetch("/command", {
    method: "POST",
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function getTask(taskId: string): Promise<TaskResponse> {
  const res = await apiFetch(`/task/${taskId}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function listTasks(limit = 20): Promise<{ tasks: TaskResponse[] }> {
  const res = await apiFetch(`/tasks?limit=${limit}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function deleteTask(taskId: string): Promise<void> {
  const res = await apiFetch(`/task/${taskId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function retryTask(taskId: string): Promise<TaskResponse> {
  const res = await apiFetch(`/task/${taskId}/retry`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function continueTaskWithAi(taskId: string): Promise<TaskResponse> {
  const res = await apiFetch(`/task/${taskId}/continue-ai`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function deleteTasks(taskIds: string[]): Promise<void> {
  const res = await apiFetch("/tasks/delete", {
    method: "POST",
    body: JSON.stringify({ task_ids: taskIds }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function pollUntilDone(
  taskId: string,
  onUpdate?: (task: TaskResponse) => void,
  intervalMs = 1000,
  maxAttempts = 30
): Promise<TaskResponse> {
  for (let i = 0; i < maxAttempts; i++) {
    const task = await getTask(taskId);
    onUpdate?.(task);
    if (
      task.status === "done" ||
      task.status === "failed" ||
      task.status === "approval_required" ||
      task.status === "cancelled"
    ) {
      return task;
    }
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  throw new Error("polling timeout");
}

export async function listApprovals(): Promise<{ approvals: ApprovalItem[] }> {
  const res = await apiFetch("/approvals");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function approveTask(taskId: string): Promise<void> {
  const res = await apiFetch(`/approval/${taskId}`, {
    method: "POST",
    body: JSON.stringify({ action: "approve" }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function rejectTask(taskId: string): Promise<void> {
  const res = await apiFetch(`/approval/${taskId}`, {
    method: "POST",
    body: JSON.stringify({ action: "reject" }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function listSchedules(): Promise<{ schedules: ScheduleItem[] }> {
  const res = await apiFetch("/schedules");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function createSchedule(input: {
  name: string;
  command: string;
  cron: string;
}): Promise<{ schedule_id: string; status: string }> {
  const res = await apiFetch("/schedule", {
    method: "POST",
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function deleteSchedule(scheduleId: string): Promise<void> {
  const res = await apiFetch(`/schedule/${scheduleId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function getSetupStatus(): Promise<SetupStatusResponse> {
  const res = await localApiFetch("/setup/status");
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function updatePermission(permissionId: string, granted: boolean): Promise<void> {
  const res = await localApiFetch("/setup/permissions", {
    method: "POST",
    body: JSON.stringify({ permission_id: permissionId, granted }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function updateConnection(
  connectionId: string,
  input: {
    configured?: boolean;
    verified?: boolean;
    account_label?: string | null;
    available?: boolean;
    metadata?: Record<string, unknown>;
  }
): Promise<{ success: boolean; connection?: ConnectionItem; error?: string }> {
  const res = await localApiFetch(`/setup/connections/${connectionId}`, {
    method: "POST",
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function disconnectTunnel(): Promise<void> {
  const res = await localApiFetch("/setup/tunnel", {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function sendTestMobileNotification(input?: {
  title?: string;
  body?: string;
}): Promise<void> {
  const res = await localApiFetch("/mobile/notifications/test", {
    method: "POST",
    body: JSON.stringify(input ?? {}),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

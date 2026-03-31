import { PairingData } from "./storage";

export interface SubmitSharedCommandResult {
  taskId?: string;
  status?: string;
}

export async function submitSharedCommand(
  pairing: PairingData,
  text: string
): Promise<SubmitSharedCommandResult> {
  const response = await fetch(`${pairing.url}/command`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${pairing.token}`,
    },
    body: JSON.stringify({
      text,
      context: {
        source: "mobile_share",
      },
    }),
  });

  let payload: Record<string, unknown> | null = null;
  try {
    payload = (await response.json()) as Record<string, unknown>;
  } catch {
    payload = null;
  }

  if (!response.ok) {
    const detail =
      typeof payload?.detail === "string"
        ? payload.detail
        : typeof payload?.error === "string"
          ? payload.error
          : `HTTP ${response.status}`;
    throw new Error(detail);
  }

  return {
    taskId: typeof payload?.task_id === "string" ? payload.task_id : undefined,
    status: typeof payload?.status === "string" ? payload.status : undefined,
  };
}

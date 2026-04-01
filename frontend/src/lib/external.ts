function isTauriRuntime(): boolean {
  if (typeof window === "undefined") return false;
  return Boolean((window as typeof window & { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__);
}

export async function openExternalUrl(url: string): Promise<void> {
  if (!url) return;

  if (isTauriRuntime()) {
    const tauriWindow = window as typeof window & {
      __TAURI_INTERNALS__?: {
        invoke?: (cmd: string, args?: Record<string, unknown>) => Promise<unknown>;
      };
    };
    const invoke = tauriWindow.__TAURI_INTERNALS__?.invoke;
    if (invoke) {
      await invoke("open_external_url", { url });
      return;
    }
  }

  if (typeof window !== "undefined") {
    window.open(url, "_blank", "noopener,noreferrer");
  }
}

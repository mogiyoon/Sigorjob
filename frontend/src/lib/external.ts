declare global {
  interface Window {
    __TAURI_INTERNALS__?: {
      invoke?: <T>(command: string, args?: Record<string, unknown>) => Promise<T>;
    };
  }
}

function isTauriWindow(): boolean {
  if (typeof window === "undefined") return false;
  return typeof window.__TAURI_INTERNALS__?.invoke === "function";
}

export async function openExternalUrl(url: string): Promise<void> {
  if (!url) return;

  if (isTauriWindow()) {
    await window.__TAURI_INTERNALS__!.invoke!("open_external_url", { url });
    return;
  }

  window.open(url, "_blank", "noopener,noreferrer");
}

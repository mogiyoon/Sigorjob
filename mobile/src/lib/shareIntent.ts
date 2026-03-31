import { Linking, NativeEventEmitter, NativeModules, Platform } from "react-native";

const bridge = NativeModules.ShareIntentBridge as
  | {
      getPendingSharedText: () => Promise<string | null>;
      addListener: (eventName: string) => void;
      removeListeners: (count: number) => void;
    }
  | undefined;

const emitter = bridge ? new NativeEventEmitter(bridge) : null;

export async function getPendingSharedText(): Promise<string | null> {
  if (Platform.OS === "ios") {
    const initialUrl = await Linking.getInitialURL();
    return extractSharedTextFromUrl(initialUrl);
  }
  if (Platform.OS !== "android" || !bridge) return null;
  const text = await bridge.getPendingSharedText();
  return typeof text === "string" && text.trim().length > 0 ? text.trim() : null;
}

export function subscribeToSharedText(listener: (text: string) => void): (() => void) | undefined {
  if (Platform.OS === "ios") {
    const subscription = Linking.addEventListener("url", ({ url }) => {
      const text = extractSharedTextFromUrl(url);
      if (text) listener(text);
    });
    return () => subscription.remove();
  }
  if (Platform.OS !== "android" || !emitter) return undefined;
  const subscription = emitter.addListener("shareTextReceived", (value: unknown) => {
    if (typeof value !== "string") return;
    const text = value.trim();
    if (!text) return;
    listener(text);
  });
  return () => subscription.remove();
}

function extractSharedTextFromUrl(url: string | null): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "sigorjob:") return null;
    if (parsed.hostname !== "share") return null;
    const text = parsed.searchParams.get("text")?.trim();
    return text || null;
  } catch {
    return null;
  }
}

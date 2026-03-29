import { NativeModules, PermissionsAndroid, Platform } from "react-native";

const bridge = NativeModules.NotificationBridge as
  | {
      savePairingConfig: (url: string, token: string) => Promise<boolean>;
      clearPairingConfig: () => Promise<boolean>;
      showLocalNotification: (title: string, body: string) => Promise<boolean>;
      startBackgroundSync: () => Promise<boolean>;
      stopBackgroundSync: () => Promise<boolean>;
    }
  | undefined;

export async function requestNotificationPermission(): Promise<boolean> {
  if (Platform.OS === "ios") {
    return true;
  }
  if (Platform.OS !== "android") return false;
  if (Platform.Version < 33) return true;
  const result = await PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS);
  return result === PermissionsAndroid.RESULTS.GRANTED;
}

export async function savePairingForNotifications(url: string, token: string): Promise<void> {
  if (!bridge) return;
  await bridge.savePairingConfig(url, token);
}

export async function clearPairingForNotifications(): Promise<void> {
  if (!bridge) return;
  await bridge.clearPairingConfig();
}

export async function showLocalNotification(title: string, body: string): Promise<void> {
  if (!bridge) return;
  await bridge.showLocalNotification(title, body);
}

export async function startBackgroundNotificationSync(): Promise<void> {
  if (!bridge) return;
  await bridge.startBackgroundSync();
}

export async function stopBackgroundNotificationSync(): Promise<void> {
  if (!bridge) return;
  await bridge.stopBackgroundSync();
}

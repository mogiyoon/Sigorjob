import AsyncStorage from "@react-native-async-storage/async-storage";
import { clearPairingForNotifications } from "./notifications";

const PAIRING_KEY = "pairing_data";

export interface PairingData {
  url: string;
  token: string;
}

export async function savePairing(data: PairingData): Promise<void> {
  await AsyncStorage.setItem(PAIRING_KEY, JSON.stringify(data));
}

export async function loadPairing(): Promise<PairingData | null> {
  const raw = await AsyncStorage.getItem(PAIRING_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PairingData;
  } catch {
    return null;
  }
}

export async function clearPairing(): Promise<void> {
  await AsyncStorage.removeItem(PAIRING_KEY);
  await clearPairingForNotifications();
}

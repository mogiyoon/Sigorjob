import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Alert,
  ActivityIndicator,
  TouchableOpacity,
} from "react-native";
import { Camera, useCameraDevice, useCodeScanner } from "react-native-vision-camera";
import { savePairing } from "../lib/storage";
import { MobileLanguage, t } from "../lib/i18n";

interface Props {
  onPaired: () => void;
  onManualEntry: () => void;
  language: MobileLanguage;
  onLanguageChange: (language: MobileLanguage) => void;
}

export default function QRScanScreen({
  onPaired,
  onManualEntry,
  language,
  onLanguageChange,
}: Props) {
  const [scanning, setScanning] = useState(true);
  const [saving, setSaving] = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const device = useCameraDevice("back");

  useEffect(() => {
    let mounted = true;

    async function ensurePermission() {
      const status = await Camera.getCameraPermissionStatus();
      if (status === "granted") {
        if (mounted) {
          setCameraReady(true);
          setPermissionDenied(false);
        }
        return;
      }

      const nextStatus = await Camera.requestCameraPermission();
      if (!mounted) return;
      if (nextStatus === "granted") {
        setCameraReady(true);
        setPermissionDenied(false);
        return;
      }
      setPermissionDenied(true);
    }

    ensurePermission();
    return () => {
      mounted = false;
    };
  }, []);

  const codeScanner = useCodeScanner({
    codeTypes: ["qr"],
    onCodeScanned: async (codes) => {
      if (!scanning || saving) return;
      const code = codes[0]?.value;
      if (!code) return;

      setScanning(false);
      setSaving(true);

      try {
        const decoded = Buffer.from(code, "base64").toString("utf-8");
        const data = JSON.parse(decoded) as { url: string; token: string };

        if (!data.url || !data.token) {
          throw new Error(t(language, "invalid_qr"));
        }
        if (!data.url.startsWith("https://")) {
          throw new Error(t(language, "invalid_https"));
        }
        if (data.token.length < 32) {
          throw new Error(t(language, "invalid_token"));
        }

        await savePairing({ url: data.url, token: data.token });
        onPaired();
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : t(language, "qr_parse_error");
        Alert.alert(t(language, "connection_failed"), msg, [
          {
            text: t(language, "try_again"),
            onPress: () => {
              setScanning(true);
              setSaving(false);
            },
          },
        ]);
      }
    },
  });

  if (permissionDenied) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{t(language, "qr_camera_permission_needed")}</Text>
        <TouchableOpacity style={styles.manualButton} onPress={onManualEntry}>
          <Text style={styles.manualButtonText}>{t(language, "manual_reconnect")}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (!cameraReady || !device) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color="#4ade80" />
        <Text style={styles.errorText}>{t(language, "camera_preparing")}</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Camera
        style={StyleSheet.absoluteFill}
        device={device}
        isActive={scanning}
        codeScanner={codeScanner}
      />

      <View style={styles.overlay}>
        <View style={styles.languageToggle}>
          <TouchableOpacity
            style={[styles.languageButton, language === "ko" && styles.languageButtonActive]}
            onPress={() => onLanguageChange("ko")}
          >
            <Text style={[styles.languageButtonText, language === "ko" && styles.languageButtonTextActive]}>
              KO
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.languageButton, language === "en" && styles.languageButtonActive]}
            onPress={() => onLanguageChange("en")}
          >
            <Text style={[styles.languageButtonText, language === "en" && styles.languageButtonTextActive]}>
              EN
            </Text>
          </TouchableOpacity>
        </View>

        <Text style={styles.title}>{t(language, "pair_with_pc")}</Text>
        <Text style={styles.subtitle}>{t(language, "scan_qr_desc")}</Text>

        <View style={styles.scanFrame} />

        {saving && (
          <View style={styles.savingBox}>
            <ActivityIndicator color="#fff" />
            <Text style={styles.savingText}>{t(language, "connecting")}</Text>
          </View>
        )}

        {!saving && (
          <TouchableOpacity style={styles.manualButton} onPress={onManualEntry}>
            <Text style={styles.manualButtonText}>{t(language, "manual_reconnect")}</Text>
          </TouchableOpacity>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#000" },
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#000",
  },
  errorText: { color: "#fff", fontSize: 16 },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: "center",
    paddingTop: 80,
  },
  languageToggle: {
    position: "absolute",
    top: 18,
    right: 18,
    flexDirection: "row",
    borderRadius: 999,
    backgroundColor: "rgba(15,23,42,0.72)",
    borderWidth: 1,
    borderColor: "rgba(148,163,184,0.24)",
    overflow: "hidden",
  },
  languageButton: {
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  languageButtonActive: {
    backgroundColor: "#f8fafc",
  },
  languageButtonText: {
    color: "#cbd5e1",
    fontSize: 12,
    fontWeight: "700",
  },
  languageButtonTextActive: {
    color: "#0f172a",
  },
  title: {
    color: "#fff",
    fontSize: 22,
    fontWeight: "bold",
    marginBottom: 8,
  },
  subtitle: {
    color: "rgba(255,255,255,0.7)",
    fontSize: 14,
    textAlign: "center",
    paddingHorizontal: 32,
    marginBottom: 40,
  },
  scanFrame: {
    width: 240,
    height: 240,
    borderWidth: 2,
    borderColor: "#4ade80",
    borderRadius: 12,
    backgroundColor: "transparent",
  },
  savingBox: {
    marginTop: 32,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    backgroundColor: "rgba(0,0,0,0.6)",
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 24,
  },
  savingText: { color: "#fff", fontSize: 16 },
  manualButton: {
    marginTop: 24,
    paddingHorizontal: 18,
    paddingVertical: 10,
    borderRadius: 999,
    borderWidth: 1,
    borderColor: "rgba(255,255,255,0.35)",
    backgroundColor: "rgba(15,23,42,0.55)",
  },
  manualButtonText: {
    color: "#e2e8f0",
    fontSize: 14,
    fontWeight: "600",
  },
});

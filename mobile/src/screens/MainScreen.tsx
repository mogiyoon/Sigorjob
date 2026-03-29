import React, { useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
} from "react-native";
import { WebView, WebViewNavigation } from "react-native-webview";
import { clearPairing, PairingData } from "../lib/storage";
import { getUrlOrigin } from "../lib/url";
import { MobileLanguage, t } from "../lib/i18n";
import {
  savePairingForNotifications,
  showLocalNotification,
  startBackgroundNotificationSync,
} from "../lib/notifications";

interface Props {
  pairing: PairingData;
  onUnpair: () => void;
  onManualRecovery: () => void;
  language: MobileLanguage;
  onLanguageChange: (language: MobileLanguage) => void;
}

export default function MainScreen({
  pairing,
  onUnpair,
  onManualRecovery,
  language,
  onLanguageChange,
}: Props) {
  const webviewRef = useRef<WebView>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [toolsOpen, setToolsOpen] = useState(false);
  const seenNotificationIds = useRef<Set<string>>(new Set());
  const didLoadSuccessfully = useRef(false);

  const initialUrl = `${pairing.url}/?_token=${encodeURIComponent(pairing.token)}`;
  const localeInjection = `
    try {
      window.localStorage.setItem('sigorjob-locale', '${language}');
      window.localStorage.setItem('agent-platform-locale', '${language}');
      document.documentElement.lang = '${language}';
    } catch (e) {}
    true;
  `;

  useEffect(() => {
    didLoadSuccessfully.current = false;
    setError(false);
    setErrorMessage("");
    setLoading(true);
    setToolsOpen(false);
  }, [pairing.token, pairing.url]);

  function handleNavigationChange(nav: WebViewNavigation) {
    const allowedOrigin = getUrlOrigin(pairing.url);
    try {
      const destinationOrigin = getUrlOrigin(nav.url);
      if (destinationOrigin !== allowedOrigin && nav.url !== "about:blank") {
        webviewRef.current?.stopLoading();
        webviewRef.current?.goBack();
      }
    } catch {
      // no-op
    }
  }

  function handleUnpair() {
    Alert.alert(t(language, "disconnect_title"), t(language, "disconnect_desc"), [
      { text: t(language, "cancel"), style: "cancel" },
      {
        text: t(language, "disconnect"),
        style: "destructive",
        onPress: async () => {
          await clearPairing();
          onUnpair();
        },
      },
    ]);
  }

  function handleConnectionLost(message?: string) {
    setLoading(false);
    setError(true);
    setErrorMessage(message || t(language, "reconnect_default"));
  }

  useEffect(() => {
    async function registerPairingForNotifications() {
      try {
        await savePairingForNotifications(pairing.url, pairing.token);
        await startBackgroundNotificationSync();
      } catch {
        // Keep WebView usable even if notification setup fails.
      }
    }

    registerPairingForNotifications();
  }, [pairing.token, pairing.url]);

  useEffect(() => {
    const fallback = setTimeout(() => {
      if (!didLoadSuccessfully.current) {
        handleConnectionLost(t(language, "loading_too_long"));
      } else {
        setLoading(false);
      }
    }, 12000);

    return () => {
      clearTimeout(fallback);
    };
  }, [pairing.token, pairing.url, language]);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    let cancelled = false;

    async function pollNotifications() {
      try {
        const res = await fetch(`${pairing.url}/mobile/notifications?limit=10`, {
          headers: {
            Authorization: `Bearer ${pairing.token}`,
          },
        });
        if (!res.ok) return;
        const payload = (await res.json()) as {
          notifications?: { id: string; title: string; body: string }[];
        };
        const notifications = payload.notifications ?? [];
        const unseen = notifications.filter((item) => !seenNotificationIds.current.has(item.id));
        for (const item of unseen) {
          seenNotificationIds.current.add(item.id);
          await showLocalNotification(item.title, item.body);
        }
        if (unseen.length > 0) {
          await fetch(`${pairing.url}/mobile/notifications/ack`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${pairing.token}`,
            },
            body: JSON.stringify({ ids: unseen.map((item) => item.id) }),
          });
        }
      } catch {
        // ignore polling errors
      }
    }

    pollNotifications();
    timer = setInterval(() => {
      if (!cancelled) pollNotifications();
    }, 10000);

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, [pairing.token, pairing.url]);

  useEffect(() => {
    if (error) return;
    webviewRef.current?.injectJavaScript(`
      try {
        window.localStorage.setItem('sigorjob-locale', '${language}');
        window.localStorage.setItem('agent-platform-locale', '${language}');
        document.documentElement.lang = '${language}';
      } catch (e) {}
      true;
    `);
    webviewRef.current?.reload();
  }, [error, language]);

  return (
    <View style={styles.container}>
      {error && (
        <View style={styles.errorContainer}>
          <LanguageToggle language={language} onChange={onLanguageChange} />
          <Text style={styles.errorTitle}>{t(language, "reconnect_title")}</Text>
          <Text style={styles.errorSub}>
            {errorMessage}
            {"\n\n"}
            {t(language, "tunnel_url")}: {pairing.url}
          </Text>
          <TouchableOpacity
            style={styles.retryBtn}
            onPress={() => {
              setError(false);
              setLoading(true);
              webviewRef.current?.reload();
            }}
          >
            <Text style={styles.retryText}>{t(language, "reconnect_current")}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.scanBtn} onPress={handleUnpair}>
            <Text style={styles.scanText}>{t(language, "qr_rescan")}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.unpairBtn} onPress={handleUnpair}>
            <Text style={styles.unpairText}>{t(language, "disconnect")}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.manualBtn} onPress={onManualRecovery}>
            <Text style={styles.manualText}>{t(language, "manual_reconnect")}</Text>
          </TouchableOpacity>
        </View>
      )}

      {!error && (
        <WebView
          ref={webviewRef}
          source={{ uri: initialUrl }}
          style={styles.webview}
          injectedJavaScriptBeforeContentLoaded={localeInjection}
          onLoadStart={() => setLoading(true)}
          onLoadEnd={() => {
            didLoadSuccessfully.current = true;
            setLoading(false);
          }}
          onLoadProgress={({ nativeEvent }) => {
            if (nativeEvent.progress >= 0.6) {
              didLoadSuccessfully.current = true;
              setLoading(false);
            }
          }}
          onError={() => {
            handleConnectionLost();
          }}
          onHttpError={(e) => {
            if (e.nativeEvent.statusCode === 401) {
              Alert.alert(t(language, "auth_expired"), t(language, "auth_expired_desc"), [
                { text: t(language, "confirm"), onPress: handleUnpair },
              ]);
              return;
            }
            handleConnectionLost(
              `${t(language, "connection_failed")}. HTTP ${e.nativeEvent.statusCode}`
            );
          }}
          onNavigationStateChange={handleNavigationChange}
          originWhitelist={[pairing.url.split("/").slice(0, 3).join("/")]}
          allowsInlineMediaPlayback={false}
          mediaPlaybackRequiresUserAction={true}
          webviewDebuggingEnabled={__DEV__}
          javaScriptEnabled={true}
          domStorageEnabled={true}
        />
      )}

      {!error && !loading && (
        <View style={styles.floatingTools}>
          {toolsOpen && (
            <View style={styles.toolsMenu}>
              <TouchableOpacity style={styles.toolsActionPrimary} onPress={handleUnpair}>
                <Text style={styles.toolsActionPrimaryText}>{t(language, "qr_rescan")}</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.toolsActionSecondary} onPress={onManualRecovery}>
                <Text style={styles.toolsActionSecondaryText}>{t(language, "manual_reconnect")}</Text>
              </TouchableOpacity>
            </View>
          )}
          <TouchableOpacity
            style={[styles.toolsFab, toolsOpen && styles.toolsFabActive]}
            onPress={() => setToolsOpen((prev) => !prev)}
          >
            <Text style={[styles.toolsFabText, toolsOpen && styles.toolsFabTextActive]}>
              {t(language, "connection_tools")}
            </Text>
          </TouchableOpacity>
        </View>
      )}

      {loading && !error && (
        <View style={styles.loadingOverlay}>
          <LanguageToggle language={language} onChange={onLanguageChange} />
          <ActivityIndicator size="large" color="#4ade80" />
          <Text style={styles.loadingText}>{t(language, "connecting")}</Text>
          <Text style={styles.loadingHint}>{t(language, "first_connection_hint")}</Text>
          <View style={styles.loadingActions}>
            <TouchableOpacity style={styles.loadingActionPrimary} onPress={handleUnpair}>
              <Text style={styles.loadingActionPrimaryText}>{t(language, "qr_rescan")}</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.loadingActionSecondary} onPress={onManualRecovery}>
              <Text style={styles.loadingActionSecondaryText}>{t(language, "manual_reconnect")}</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}
    </View>
  );
}

function LanguageToggle({
  language,
  onChange,
}: {
  language: MobileLanguage;
  onChange: (language: MobileLanguage) => void;
}) {
  return (
    <View style={styles.languageToggle}>
      <TouchableOpacity
        style={[styles.languageButton, language === "ko" && styles.languageButtonActive]}
        onPress={() => onChange("ko")}
      >
        <Text style={[styles.languageButtonText, language === "ko" && styles.languageButtonTextActive]}>
          KO
        </Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.languageButton, language === "en" && styles.languageButtonActive]}
        onPress={() => onChange("en")}
      >
        <Text style={[styles.languageButtonText, language === "en" && styles.languageButtonTextActive]}>
          EN
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#0f172a" },
  webview: { flex: 1 },
  languageToggle: {
    position: "absolute",
    top: 16,
    left: 16,
    flexDirection: "row",
    borderRadius: 999,
    backgroundColor: "rgba(15,23,42,0.72)",
    borderWidth: 1,
    borderColor: "rgba(148,163,184,0.22)",
    overflow: "hidden",
    zIndex: 3,
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
  floatingTools: {
    position: "absolute",
    top: 16,
    right: 16,
    alignItems: "flex-end",
    gap: 10,
  },
  toolsMenu: {
    gap: 8,
    padding: 10,
    borderRadius: 20,
    backgroundColor: "rgba(15,23,42,0.7)",
    borderWidth: 1,
    borderColor: "rgba(148,163,184,0.18)",
  },
  toolsActionPrimary: {
    backgroundColor: "#67e8f9",
    minHeight: 38,
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderRadius: 999,
    justifyContent: "center",
    alignItems: "center",
  },
  toolsActionPrimaryText: {
    color: "#082f49",
    fontSize: 12,
    fontWeight: "700",
  },
  toolsActionSecondary: {
    backgroundColor: "rgba(15,23,42,0.92)",
    borderWidth: 1,
    borderColor: "rgba(226,232,240,0.18)",
    minHeight: 38,
    paddingHorizontal: 14,
    paddingVertical: 9,
    borderRadius: 999,
    justifyContent: "center",
    alignItems: "center",
  },
  toolsActionSecondaryText: {
    color: "#e2e8f0",
    fontSize: 12,
    fontWeight: "600",
  },
  toolsFab: {
    minHeight: 40,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 999,
    backgroundColor: "rgba(15,23,42,0.82)",
    borderWidth: 1,
    borderColor: "rgba(148,163,184,0.24)",
    justifyContent: "center",
    alignItems: "center",
  },
  toolsFabActive: {
    backgroundColor: "#f8fafc",
  },
  toolsFabText: {
    color: "#e2e8f0",
    fontSize: 12,
    fontWeight: "700",
  },
  toolsFabTextActive: {
    color: "#0f172a",
  },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "#0f172a",
    justifyContent: "center",
    alignItems: "center",
    gap: 16,
  },
  loadingText: { color: "#94a3b8", fontSize: 14 },
  loadingHint: {
    color: "#64748b",
    fontSize: 12,
  },
  loadingActions: {
    marginTop: 14,
    flexDirection: "row",
    gap: 12,
  },
  loadingActionPrimary: {
    backgroundColor: "#67e8f9",
    minHeight: 46,
    paddingHorizontal: 18,
    paddingVertical: 12,
    borderRadius: 999,
    justifyContent: "center",
    alignItems: "center",
  },
  loadingActionPrimaryText: {
    color: "#082f49",
    fontSize: 14,
    fontWeight: "700",
  },
  loadingActionSecondary: {
    borderWidth: 1,
    borderColor: "rgba(226,232,240,0.2)",
    backgroundColor: "rgba(15,23,42,0.72)",
    minHeight: 46,
    paddingHorizontal: 18,
    paddingVertical: 12,
    borderRadius: 999,
    justifyContent: "center",
    alignItems: "center",
  },
  loadingActionSecondaryText: {
    color: "#e2e8f0",
    fontSize: 14,
    fontWeight: "600",
  },
  errorContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 32,
    gap: 16,
  },
  errorTitle: {
    color: "#f1f5f9",
    fontSize: 22,
    fontWeight: "bold",
  },
  errorSub: {
    color: "#94a3b8",
    fontSize: 14,
    textAlign: "center",
    lineHeight: 22,
  },
  retryBtn: {
    marginTop: 10,
    backgroundColor: "#4ade80",
    minHeight: 48,
    paddingHorizontal: 32,
    paddingVertical: 13,
    borderRadius: 999,
    justifyContent: "center",
    alignItems: "center",
  },
  retryText: { color: "#0f172a", fontWeight: "bold", fontSize: 16 },
  scanBtn: {
    backgroundColor: "#67e8f9",
    minHeight: 48,
    paddingHorizontal: 28,
    paddingVertical: 13,
    borderRadius: 999,
    justifyContent: "center",
    alignItems: "center",
  },
  scanText: {
    color: "#082f49",
    fontWeight: "700",
    fontSize: 15,
  },
  manualBtn: {
    paddingHorizontal: 24,
    paddingVertical: 10,
    borderRadius: 999,
    backgroundColor: "rgba(15,23,42,0.5)",
    borderWidth: 1,
    borderColor: "rgba(226,232,240,0.18)",
  },
  manualText: { color: "#e2e8f0", fontSize: 14 },
  unpairBtn: {
    paddingHorizontal: 24,
    paddingVertical: 6,
  },
  unpairText: { color: "#ef4444", fontSize: 14 },
});

import React, { useEffect, useState } from "react";
import { StatusBar, View, StyleSheet, Text, ActivityIndicator, TouchableOpacity } from "react-native";
import { clearPairing, loadPairing, PairingData } from "./src/lib/storage";
import { requestNotificationPermission } from "./src/lib/notifications";
import { loadMobileLanguage, MobileLanguage, saveMobileLanguage, t } from "./src/lib/i18n";
import QRScanScreen from "./src/screens/QRScanScreen";
import MainScreen from "./src/screens/MainScreen";
import ManualPairScreen from "./src/screens/ManualPairScreen";

type Screen = "loading" | "scan" | "manual" | "main" | "error";

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

export default function App() {
  const [screen, setScreen] = useState<Screen>("loading");
  const [pairing, setPairing] = useState<PairingData | null>(null);
  const [startupError, setStartupError] = useState<string | null>(null);
  const [language, setLanguage] = useState<MobileLanguage>("ko");

  useEffect(() => {
    let mounted = true;

    async function bootstrap() {
      try {
        const nextLanguage = await loadMobileLanguage();
        if (mounted) setLanguage(nextLanguage);

        await requestNotificationPermission().catch(() => {});
        const data = await loadPairing();
        if (!mounted) return;

        if (data) {
          setPairing(data);
          setScreen("main");
          return;
        }
        setScreen("scan");
      } catch (error: unknown) {
        if (!mounted) return;
        const message = error instanceof Error ? error.message : t(language, "app_start_failed_desc");
        setStartupError(message);
        setScreen("error");
      }
    }

    bootstrap();

    return () => {
      mounted = false;
    };
  }, []);

  async function handleLanguageChange(nextLanguage: MobileLanguage) {
    setLanguage(nextLanguage);
    await saveMobileLanguage(nextLanguage);
  }

  function handlePaired() {
    loadPairing().then((data) => {
      if (data) {
        setPairing(data);
        setScreen("main");
      }
    });
  }

  function handleUnpair() {
    setPairing(null);
    setScreen("scan");
  }

  async function handleRecoverToManual() {
    await clearPairing();
    setPairing(null);
    setScreen("manual");
  }

  if (screen === "loading") {
    return (
      <View style={styles.loading}>
        <LanguageToggle language={language} onChange={handleLanguageChange} />
        <ActivityIndicator size="large" color="#4ade80" />
        <Text style={styles.loadingText}>{t(language, "app_starting")}</Text>
      </View>
    );
  }

  if (screen === "error") {
    return (
      <View style={styles.errorScreen}>
        <LanguageToggle language={language} onChange={handleLanguageChange} />
        <Text style={styles.errorTitle}>{t(language, "app_start_failed")}</Text>
        <Text style={styles.errorDescription}>
          {startupError ?? t(language, "app_start_failed_desc")}
        </Text>
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={() => {
            setStartupError(null);
            setScreen("manual");
          }}
        >
          <Text style={styles.primaryButtonText}>{t(language, "start_manual")}</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.secondaryButton}
          onPress={() => {
            setStartupError(null);
            setScreen("scan");
          }}
        >
          <Text style={styles.secondaryButtonText}>{t(language, "retry_with_qr")}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <>
      <StatusBar barStyle="light-content" backgroundColor="#0f172a" />
      {screen === "scan" && (
        <QRScanScreen
          language={language}
          onLanguageChange={handleLanguageChange}
          onPaired={handlePaired}
          onManualEntry={() => setScreen("manual")}
        />
      )}
      {screen === "manual" && (
        <ManualPairScreen
          language={language}
          onLanguageChange={handleLanguageChange}
          onPaired={handlePaired}
          onBack={() => setScreen("scan")}
        />
      )}
      {screen === "main" && pairing && (
        <MainScreen
          language={language}
          onLanguageChange={handleLanguageChange}
          pairing={pairing}
          onUnpair={handleUnpair}
          onManualRecovery={handleRecoverToManual}
        />
      )}
    </>
  );
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    backgroundColor: "#0f172a",
    justifyContent: "center",
    alignItems: "center",
    gap: 14,
  },
  loadingText: {
    color: "#cbd5e1",
    fontSize: 15,
  },
  errorScreen: {
    flex: 1,
    backgroundColor: "#0f172a",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 28,
    gap: 16,
  },
  errorTitle: {
    color: "#f8fafc",
    fontSize: 22,
    fontWeight: "700",
    textAlign: "center",
  },
  errorDescription: {
    color: "#94a3b8",
    fontSize: 14,
    textAlign: "center",
    lineHeight: 22,
  },
  primaryButton: {
    marginTop: 8,
    backgroundColor: "#4ade80",
    paddingHorizontal: 22,
    paddingVertical: 12,
    borderRadius: 999,
  },
  primaryButtonText: {
    color: "#052e16",
    fontSize: 15,
    fontWeight: "700",
  },
  secondaryButton: {
    paddingVertical: 8,
  },
  secondaryButtonText: {
    color: "#cbd5e1",
    fontSize: 14,
    fontWeight: "600",
  },
  languageToggle: {
    position: "absolute",
    top: 20,
    right: 20,
    flexDirection: "row",
    borderRadius: 999,
    backgroundColor: "rgba(15,23,42,0.6)",
    borderWidth: 1,
    borderColor: "rgba(148,163,184,0.2)",
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
});

import React, { useState } from "react";
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";
import { savePairing } from "../lib/storage";
import { getUrlOrigin } from "../lib/url";
import { MobileLanguage, t } from "../lib/i18n";

interface Props {
  onBack: () => void;
  onPaired: () => void;
  language: MobileLanguage;
  onLanguageChange: (language: MobileLanguage) => void;
}

export default function ManualPairScreen({
  onBack,
  onPaired,
  language,
  onLanguageChange,
}: Props) {
  const [url, setUrl] = useState("");
  const [token, setToken] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit() {
    if (saving) return;

    const trimmedUrl = url.trim();
    const trimmedToken = token.trim();

    try {
      const origin = getUrlOrigin(trimmedUrl);
      if (!origin.startsWith("https://")) {
        throw new Error(t(language, "invalid_https"));
      }
      if (trimmedToken.length < 32) {
        throw new Error(t(language, "token_too_short"));
      }

      setSaving(true);
      await savePairing({ url: origin, token: trimmedToken });
      onPaired();
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : t(language, "check_connection_info");
      Alert.alert(t(language, "connection_failed"), message);
      setSaving(false);
    }
  }

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      style={styles.container}
    >
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

      <View style={styles.content}>
        <Text style={styles.title}>{t(language, "connect_manually")}</Text>
        <Text style={styles.subtitle}>{t(language, "manual_desc")}</Text>

        <View style={styles.field}>
          <Text style={styles.label}>{t(language, "tunnel_url")}</Text>
          <TextInput
            value={url}
            onChangeText={setUrl}
            autoCapitalize="none"
            autoCorrect={false}
            placeholder="https://example.trycloudflare.com"
            placeholderTextColor="#64748b"
            style={styles.input}
          />
        </View>

        <View style={styles.field}>
          <Text style={styles.label}>{t(language, "auth_token")}</Text>
          <TextInput
            value={token}
            onChangeText={setToken}
            autoCapitalize="none"
            autoCorrect={false}
            placeholder={t(language, "paste_token")}
            placeholderTextColor="#64748b"
            style={[styles.input, styles.textarea]}
            multiline
          />
        </View>

        <TouchableOpacity
          style={[styles.primaryButton, (!url.trim() || !token.trim() || saving) && styles.disabled]}
          disabled={!url.trim() || !token.trim() || saving}
          onPress={handleSubmit}
        >
          <Text style={styles.primaryButtonText}>
            {saving ? t(language, "saving") : t(language, "connect")}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.secondaryButton} onPress={onBack}>
          <Text style={styles.secondaryButtonText}>{t(language, "back_to_qr")}</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f172a",
    justifyContent: "center",
    paddingHorizontal: 24,
  },
  content: {
    gap: 18,
  },
  languageToggle: {
    position: "absolute",
    top: 20,
    right: 24,
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
  title: {
    color: "#f8fafc",
    fontSize: 24,
    fontWeight: "700",
  },
  subtitle: {
    color: "#94a3b8",
    fontSize: 14,
    lineHeight: 22,
  },
  field: {
    gap: 8,
  },
  label: {
    color: "#cbd5e1",
    fontSize: 13,
    fontWeight: "600",
  },
  input: {
    backgroundColor: "#111827",
    borderWidth: 1,
    borderColor: "#334155",
    color: "#f8fafc",
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  textarea: {
    minHeight: 120,
    textAlignVertical: "top",
  },
  primaryButton: {
    backgroundColor: "#4ade80",
    borderRadius: 999,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 8,
  },
  disabled: {
    opacity: 0.5,
  },
  primaryButtonText: {
    color: "#052e16",
    fontSize: 16,
    fontWeight: "700",
  },
  secondaryButton: {
    alignItems: "center",
    paddingVertical: 8,
  },
  secondaryButtonText: {
    color: "#94a3b8",
    fontSize: 14,
  },
});

"use client";

import Link from "next/link";
import { type ReactNode, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import LanguageToggle from "@/components/LanguageToggle";
import { useLanguage } from "@/components/LanguageProvider";
import { openExternalUrl } from "@/lib/external";
import {
  disconnectTunnel,
  getMcpPresets,
  getSetupStatus,
  localApiFetch,
  sendTestMobileNotification,
  type McpPresetItem,
  type SetupStatusResponse,
} from "@/lib/api";

type Step = "intro" | "token" | "connecting" | "done";
type TunnelMode = "none" | "quick" | "cloudflare";
type SetupPageData = ReturnType<typeof useSetupPageData>;

function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function formatText(template: string, values: Record<string, string | number>) {
  return Object.entries(values).reduce(
    (result, [key, value]) => result.replaceAll(`{${key}}`, String(value)),
    template
  );
}

function SetupShell({
  children,
  title,
  description,
  showOverview = true,
  status,
}: {
  children: ReactNode;
  title: string;
  description: string;
  showOverview?: boolean;
  status: SetupStatusResponse | null;
}) {
  const router = useRouter();
  const { t } = useLanguage();

  return (
    <main className="min-h-screen bg-gray-50 px-4 py-10">
      <div className="mx-auto w-full max-w-5xl space-y-6">
        <div className="flex items-center justify-between gap-4">
          <button
            onClick={() => router.push("/")}
            className="rounded-full border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
          >
            {t("back", "← Back")}
          </button>
          <LanguageToggle />
        </div>
        <section className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="space-y-1">
              <h1 className="text-2xl font-semibold tracking-tight text-gray-950">{title}</h1>
              <p className="text-sm text-gray-500">{description}</p>
            </div>
            {showOverview && (
              <div className="flex flex-wrap gap-2">
                <span
                  className={cn(
                    "rounded-full px-3 py-1 text-xs font-medium",
                    status?.tunnel_active ? "bg-emerald-50 text-emerald-800" : "bg-slate-100 text-slate-700"
                  )}
                >
                  {t("mobile_connection", "Mobile")}:{" "}
                  {status?.tunnel_active
                    ? t("connected_short", "Connected")
                    : t("disconnected_short", "Off")}
                </span>
                <span
                  className={cn(
                    "rounded-full px-3 py-1 text-xs font-medium",
                    status?.ai_verified
                      ? "bg-green-100 text-green-700"
                      : "bg-slate-100 text-slate-700"
                  )}
                >
                  AI:{" "}
                  {status?.ai_verified
                    ? t("connected_short", "Connected")
                    : t("not_connected_short", "Not connected")}
                </span>
              </div>
            )}
          </div>
        </section>
        {children}
      </div>
    </main>
  );
}

function useSetupPageData() {
  const { t } = useLanguage();
  const [openedFromSettings, setOpenedFromSettings] = useState(false);
  const [step, setStep] = useState<Step>("intro");
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [tunnelUrl, setTunnelUrl] = useState("");
  const [status, setStatus] = useState<SetupStatusResponse | null>(null);
  const [selectedMode, setSelectedMode] = useState<TunnelMode>("quick");
  const [apiKey, setApiKey] = useState("");
  const [aiSaving, setAiSaving] = useState(false);
  const [aiMessage, setAiMessage] = useState("");
  const [mobileMessage, setMobileMessage] = useState("");
  const [notificationTesting, setNotificationTesting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [showAiErrorDetails, setShowAiErrorDetails] = useState(false);
  const [mcpPresets, setMcpPresets] = useState<McpPresetItem[]>([]);

  const getFriendlyAiError = (rawError?: string | null) => {
    if (!rawError) return "";
    const normalized = rawError.toLowerCase();
    if (
      normalized.includes("credit balance is too low") ||
      normalized.includes("purchase credits") ||
      normalized.includes("billing") ||
      normalized.includes("spend limit")
    ) {
      return t(
        "ai_credit_low",
        "Your Anthropic API credits are too low. Add credits in Plans & Billing, then try verification again."
      );
    }
    if (normalized.includes("invalid x-api-key") || normalized.includes("authentication")) {
      return t(
        "ai_auth_failed",
        "Check your Anthropic API key. It may be invalid or no longer active."
      );
    }
    if (
      normalized.includes("network") ||
      normalized.includes("timed out") ||
      normalized.includes("connection") ||
      normalized.includes("dns")
    ) {
      return t(
        "ai_network_failed",
        "Could not connect to the Anthropic API. Check your network and try again."
      );
    }
    return t(
      "ai_verify_failed_generic",
      "We could not confirm AI access. Check the details and try again."
    );
  };

  const refreshStatus = async () => {
    try {
      const data = await getSetupStatus();
      setStatus(data);
      if (data.tunnel_mode) {
        setSelectedMode(data.tunnel_mode);
      }
      if (data.tunnel_active && data.tunnel_url) {
        setTunnelUrl(data.tunnel_url);
        setStep("done");
      }
    } catch {
      // Ignore initial status fetch failures.
    }
  };

  const refreshMcpPresets = async () => {
    try {
      const presets = await getMcpPresets();
      setMcpPresets(presets);
    } catch {
      // Ignore initial preset fetch failures.
    }
  };

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      setOpenedFromSettings(params.get("source") === "settings");
    }
    void refreshStatus();
    void refreshMcpPresets();
    const statusInterval = setInterval(() => {
      void refreshStatus();
    }, 3000);
    const presetInterval = setInterval(() => {
      void refreshMcpPresets();
    }, 3000);
    return () => {
      clearInterval(statusInterval);
      clearInterval(presetInterval);
    };
  }, []);

  const waitForTunnelReady = async (timeoutMs = 12000) => {
    const startedAt = Date.now();
    while (Date.now() - startedAt < timeoutMs) {
      const latest = await getSetupStatus();
      setStatus(latest);
      if (latest.tunnel_active && latest.tunnel_url) {
        setTunnelUrl(latest.tunnel_url);
        setStep("done");
        return true;
      }
      await new Promise((resolve) => setTimeout(resolve, 1500));
    }
    return false;
  };

  const handleConnect = async () => {
    if (selectedMode === "cloudflare" && !token.trim()) return;
    setStep("connecting");
    setError("");

    try {
      const res =
        selectedMode === "quick"
          ? await localApiFetch("/setup/quick", { method: "POST" })
          : await localApiFetch("/setup/cloudflare", {
              method: "POST",
              body: JSON.stringify({ cloudflare_tunnel_token: token.trim() }),
            });
      const data = await res.json();
      if (data.success) {
        setTunnelUrl(data.tunnel_url);
        setStep("done");
      } else {
        const readyAfterDelay = selectedMode === "quick" ? await waitForTunnelReady() : false;
        if (!readyAfterDelay) {
          setError(data.error ?? t("connect_failed", "Connection failed. Check your settings and try again."));
          setStep(selectedMode === "cloudflare" ? "token" : "intro");
        }
      }
    } catch {
      setError(t("backend_unreachable", "Cannot reach the backend. Make sure the app is running."));
      setStep(selectedMode === "cloudflare" ? "token" : "intro");
    }
  };

  const handleSaveAiKey = async () => {
    if (!apiKey.trim()) return;
    setAiSaving(true);
    setAiMessage("");
    try {
      const res = await localApiFetch("/setup/ai", {
        method: "POST",
        body: JSON.stringify({ anthropic_api_key: apiKey.trim() }),
      });
      const data = await res.json();
      if (data.success) {
        setApiKey("");
        setAiMessage(
          data.verified
            ? t("ai_key_saved_verified", "AI key saved and verified.")
            : getFriendlyAiError(data.validation_error) ||
                t(
                  "ai_key_saved_unverified",
                  "The AI key is saved, but real AI access has not been confirmed yet."
                )
        );
        await refreshStatus();
      } else {
        setAiMessage(getFriendlyAiError(data.error) || t("ai_key_save_failed", "Could not save the AI key."));
      }
    } catch {
      setAiMessage(t("ai_key_save_failed", "Could not save the AI key."));
    } finally {
      setAiSaving(false);
    }
  };

  const handleRemoveAiKey = async () => {
    setAiSaving(true);
    setAiMessage("");
    try {
      const res = await localApiFetch("/setup/ai", { method: "DELETE" });
      const data = await res.json();
      if (data.success) {
        setAiMessage(t("ai_key_removed", "Removed the saved AI key."));
        await refreshStatus();
      } else {
        setAiMessage(t("ai_key_remove_failed", "Could not remove the saved AI key."));
      }
    } catch {
      setAiMessage(t("ai_key_remove_failed", "Could not remove the saved AI key."));
    } finally {
      setAiSaving(false);
    }
  };

  const handleVerifyAiKey = async () => {
    setAiSaving(true);
    setAiMessage("");
    try {
      const res = await localApiFetch("/setup/ai/verify", { method: "POST" });
      const data = await res.json();
      if (data.verified) {
        setAiMessage(t("ai_verified_now", "AI is ready to use."));
      } else {
        setAiMessage(
          getFriendlyAiError(data.validation_error ?? data.error) ||
            t("ai_verify_failed_short", "Could not verify AI access.")
        );
      }
      await refreshStatus();
    } catch {
      setAiMessage(t("ai_verify_failed_short", "Could not verify AI access."));
    } finally {
      setAiSaving(false);
    }
  };

  const handleTestNotification = async () => {
    setNotificationTesting(true);
    setMobileMessage("");
    try {
      await sendTestMobileNotification({
        title: t("notification_test_title", "Sigorjob test"),
        body: t(
          "notification_test_body",
          "If your phone is connected and the app is open, you should see this in a few seconds."
        ),
      });
      setMobileMessage(
        t(
          "test_notification_sent",
          "A test notification has been queued. Keep the phone app open and wait a few seconds."
        )
      );
    } catch {
      setMobileMessage(t("test_notification_failed", "Could not send a test notification."));
    } finally {
      setNotificationTesting(false);
    }
  };

  const handleDisconnectTunnel = async () => {
    setDisconnecting(true);
    setMobileMessage("");
    setError("");
    try {
      await disconnectTunnel();
      setTunnelUrl("");
      setStatus((current) =>
        current
          ? {
              ...current,
              configured: false,
              tunnel_mode: "none",
              tunnel_active: false,
              tunnel_url: null,
            }
          : current
      );
      setSelectedMode("quick");
      setStep("intro");
      setMobileMessage(t("mobile_disconnected_message", "Phone connection has been turned off."));
      await refreshStatus();
    } catch {
      setMobileMessage(t("mobile_disconnect_failed", "Could not turn off the phone connection."));
    } finally {
      setDisconnecting(false);
    }
  };

  return {
    t,
    openedFromSettings,
    step,
    setStep,
    token,
    setToken,
    error,
    tunnelUrl,
    status,
    selectedMode,
    setSelectedMode,
    apiKey,
    setApiKey,
    aiSaving,
    aiMessage,
    mobileMessage,
    notificationTesting,
    disconnecting,
    showAiErrorDetails,
    setShowAiErrorDetails,
    mcpPresets,
    getFriendlyAiError,
    handleConnect,
    handleSaveAiKey,
    handleRemoveAiKey,
    handleVerifyAiKey,
    handleTestNotification,
    handleDisconnectTunnel,
  };
}

function getSetupSummary(status: SetupStatusResponse | null, mcpPresets: McpPresetItem[]) {
  const builtinConnections = (status?.connections ?? []).filter(
    (connection) => connection.kind === "external" && connection.driver_id !== "template_connector"
  );
  const connectedConnections = builtinConnections.filter(
    (connection) => connection.verified || connection.configured || connection.status === "connected"
  );
  const grantedPermissions = (status?.permissions ?? []).filter((permission) => permission.granted);
  const installedPresets = mcpPresets.filter((preset) => preset.installed);
  const totalToolItems = 1 + mcpPresets.length;
  const readyToolItems = Number(Boolean(status?.playwright.installed)) + installedPresets.length;

  return {
    builtinConnections,
    connectedConnections,
    grantedPermissions,
    installedPresets,
    totalToolItems,
    readyToolItems,
  };
}

function SummaryIcon({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gray-900 text-white">
      {children}
    </div>
  );
}

function ConnectionIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M8 12a4 4 0 0 1 4-4h4" strokeLinecap="round" />
      <path d="M16 12a4 4 0 0 1-4 4H8" strokeLinecap="round" />
      <path d="M9 9 6 12l3 3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="m15 9 3 3-3 3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PermissionIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M12 3 5 6v5c0 4.5 2.9 7.9 7 10 4.1-2.1 7-5.5 7-10V6l-7-3Z" strokeLinejoin="round" />
      <path d="m9.5 12 1.7 1.7 3.3-3.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ToolsIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M14 7a4 4 0 0 0 5 5l-7 7a2 2 0 0 1-3-3l7-7a4 4 0 0 0-2-2Z" strokeLinejoin="round" />
      <path d="m15 5 4 4" strokeLinecap="round" />
    </svg>
  );
}

function SummaryCard({
  icon,
  title,
  count,
  description,
  href,
  linkLabel,
}: {
  icon: ReactNode;
  title: string;
  count: string;
  description: string;
  href: string;
  linkLabel: string;
}) {
  return (
    <div className="flex h-full flex-col justify-between rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <SummaryIcon>{icon}</SummaryIcon>
          <div className="text-right">
            <p className="text-sm font-medium text-gray-500">{title}</p>
            <p className="mt-1 text-xl font-semibold tracking-tight text-gray-950">{count}</p>
          </div>
        </div>
        <p className="text-sm leading-6 text-gray-600">{description}</p>
      </div>
      <Link
        href={href}
        className="mt-5 inline-flex w-fit rounded-full border border-gray-200 bg-gray-50 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100"
      >
        {linkLabel}
      </Link>
    </div>
  );
}

function SetupSummaryCards({ data }: { data: SetupPageData }) {
  const { t, status, mcpPresets } = data;
  const summary = getSetupSummary(status, mcpPresets);
  const connectionsCount = formatText(t("setup_connections_summary_count", "{connected}/{total} connected"), {
    connected: summary.connectedConnections.length,
    total: summary.builtinConnections.length,
  });
  const permissionsCount = formatText(t("setup_permissions_summary_count", "{granted}/{total} allowed"), {
    granted: summary.grantedPermissions.length,
    total: status?.permissions.length ?? 0,
  });
  const toolsCount = formatText(t("setup_tools_summary_count", "{ready}/{total} ready"), {
    ready: summary.readyToolItems,
    total: summary.totalToolItems,
  });

  return (
    <section className="grid gap-4 md:grid-cols-3">
      <SummaryCard
        icon={<ConnectionIcon />}
        title={t("external_connections_title", "External connections")}
        count={connectionsCount}
        description={t(
          "setup_connections_summary_hint",
          "Review connected services and manage external connection details on the dedicated page."
        )}
        href="/setup/connections"
        linkLabel={t("setup_summary_view_details", "View details")}
      />
      <SummaryCard
        icon={<PermissionIcon />}
        title={t("permissions_title", "Permissions")}
        count={permissionsCount}
        description={t(
          "setup_permissions_summary_hint",
          "Open the permission page to review and change detailed allow and deny settings."
        )}
        href="/setup/permissions"
        linkLabel={t("setup_summary_view_details", "View details")}
      />
      <SummaryCard
        icon={<ToolsIcon />}
        title={t("tools_title", "Tools")}
        count={toolsCount}
        description={t(
          "setup_tools_summary_hint",
          "Check Playwright and MCP tool readiness on the dedicated tools page."
        )}
        href="/setup/tools"
        linkLabel={t("setup_summary_view_details", "View details")}
      />
    </section>
  );
}

function AiSettingsCard({ data }: { data: SetupPageData }) {
  const {
    t,
    status,
    apiKey,
    setApiKey,
    aiSaving,
    aiMessage,
    showAiErrorDetails,
    setShowAiErrorDetails,
    handleSaveAiKey,
    handleVerifyAiKey,
    handleRemoveAiKey,
    getFriendlyAiError,
  } = data;

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="space-y-4">
        <div className="space-y-1">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-semibold text-gray-900">{t("ai_fallback_setup")}</h2>
            <span
              className={cn(
                "rounded-full px-2.5 py-1 text-xs font-medium",
                status?.ai_verified ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"
              )}
            >
              {status?.ai_verified
                ? t("connected_short", "Connected")
                : t("not_connected_short", "Not connected")}
            </span>
          </div>
          <p className="text-sm text-gray-600">
            {t("ai_setup_short_desc", "Set up AI so it can continue tasks when needed.")}
          </p>
        </div>
        <div className="space-y-3 rounded-2xl border border-gray-100 bg-gray-50 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-gray-900">{t("anthropic_api_key")}</p>
              <p className="text-xs text-gray-500">{t("ai_usage_desc")}</p>
              <p className="text-xs text-gray-500">
                {t("storage_location")}:{" "}
                {status?.ai_storage_backend === "keychain"
                  ? t("keychain")
                  : t("local_secure_config", "Local secure config")}
              </p>
            </div>
            <span
              className={cn(
                "rounded-full px-2.5 py-1 text-xs font-medium",
                status?.ai_configured ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-600"
              )}
            >
              {status?.ai_configured ? t("configured") : t("not_set")}
            </span>
          </div>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-ant-..."
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={handleSaveAiKey}
              disabled={aiSaving || !apiKey.trim()}
              className="rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {aiSaving ? t("saving") : t("save_ai_key", "Save AI key")}
            </button>
            <button
              type="button"
              onClick={handleVerifyAiKey}
              disabled={aiSaving || !status?.ai_configured}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 disabled:opacity-50"
            >
              {aiSaving ? t("saving") : t("verify_connection", "Verify")}
            </button>
            {status?.ai_configured && (
              <button
                type="button"
                onClick={handleRemoveAiKey}
                disabled={aiSaving}
                className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-700 disabled:opacity-50"
              >
                {t("remove")}
              </button>
            )}
          </div>
          {aiMessage && (
            <div className="space-y-2 rounded-xl border border-gray-200 bg-white p-3">
              <p className="text-sm text-gray-700">{aiMessage}</p>
              {status?.ai_validation_error && getFriendlyAiError(status.ai_validation_error) && (
                <div className="space-y-2">
                  <button
                    type="button"
                    onClick={() => setShowAiErrorDetails((prev) => !prev)}
                    className="text-xs font-medium text-gray-600 underline underline-offset-2"
                  >
                    {showAiErrorDetails
                      ? t("hide_ai_error_details", "Hide technical details")
                      : t("show_ai_error_details", "Show technical details")}
                  </button>
                  {showAiErrorDetails && (
                    <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-gray-950 p-3 text-xs text-gray-100">
                      {status.ai_validation_error}
                    </pre>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
        <div className="space-y-3 rounded-2xl border border-gray-100 bg-gray-50 p-4">
          <div className="space-y-1">
            <p className="text-sm font-medium text-gray-900">{t("api_key_guide", "API key guide")}</p>
            <p className="text-xs text-gray-500">
              {t(
                "api_key_guide_short_desc",
                "See where each provider issues API keys before you save one here."
              )}
            </p>
          </div>
          <div className="space-y-3">
            <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-blue-900">Anthropic</p>
                  <p className="text-xs text-blue-700">{t("currently_supported")}</p>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    openExternalUrl("https://docs.anthropic.com/en/api/getting-started")
                  }
                  className="text-sm font-medium text-blue-700 underline underline-offset-2"
                >
                  {t("issuance_guide")}
                </button>
              </div>
              <p className="mt-2 text-xs leading-5 text-blue-800">{t("anthropic_issue_desc")}</p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">OpenAI</p>
                  <p className="text-xs text-gray-600">{t("reference_link")}</p>
                </div>
                <button
                  type="button"
                  onClick={() => openExternalUrl("https://platform.openai.com/docs/quickstart")}
                  className="text-sm font-medium text-gray-700 underline underline-offset-2"
                >
                  {t("issuance_guide")}
                </button>
              </div>
              <p className="mt-2 text-xs leading-5 text-gray-700">{t("openai_issue_desc")}</p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-gray-900">Google Gemini</p>
                  <p className="text-xs text-gray-600">{t("reference_link")}</p>
                </div>
                <button
                  type="button"
                  onClick={() => openExternalUrl("https://ai.google.dev/tutorials/setup")}
                  className="text-sm font-medium text-gray-700 underline underline-offset-2"
                >
                  {t("issuance_guide")}
                </button>
              </div>
              <p className="mt-2 text-xs leading-5 text-gray-700">{t("gemini_issue_desc")}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MobileOperationsCard({ data }: { data: SetupPageData }) {
  const { t, notificationTesting, disconnecting, handleTestNotification, handleDisconnectTunnel } =
    data;

  return (
    <div className="space-y-3 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="space-y-1">
        <p className="text-sm font-semibold text-gray-900">
          {t("mobile_operations", "Mobile actions")}
        </p>
        <p className="text-xs leading-5 text-gray-600">
          {t("mobile_operations_short_desc", "Send a test notification or disconnect and start again.")}
        </p>
      </div>
      <div className="flex gap-2">
        <button
          onClick={handleTestNotification}
          disabled={notificationTesting}
          className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 disabled:opacity-50"
        >
          {notificationTesting
            ? t("sending", "Sending...")
            : t("send_test_notification", "Send test notification")}
        </button>
        <button
          onClick={handleDisconnectTunnel}
          disabled={disconnecting}
          className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-700 disabled:opacity-50"
        >
          {disconnecting
            ? t("disconnecting_short", "Disconnecting...")
            : t("disconnect_mobile_connection", "Disconnect phone connection")}
        </button>
      </div>
    </div>
  );
}

function MobileSetupSection({ data }: { data: SetupPageData }) {
  const { t, status, selectedMode, setSelectedMode, setStep, handleConnect } = data;

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="space-y-4">
        <div className="space-y-1">
          <h2 className="font-semibold text-gray-900">{t("mobile_connection", "Mobile Connect")}</h2>
          <p className="text-sm text-gray-600">
            {t("mobile_setup_short_desc", "Choose a connection type and start right away.")}
          </p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-700">
          {status?.tunnel_active
            ? t("mobile_ready_desc", "The mobile connection is ready.")
            : status?.tunnel_error
              ? `${t("connection_status_label", "Status")}: ${status.tunnel_error}`
              : t(
                  "mobile_setup_status_idle",
                  "Press the button once and wait a few seconds while the connection opens."
                )}
        </div>
        <div className="space-y-3">
          <button
            onClick={() => setSelectedMode("quick")}
            className={cn(
              "w-full rounded-lg border p-4 text-left",
              selectedMode === "quick" ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-white"
            )}
          >
            <p className="font-medium text-gray-900">{t("quick_tunnel")}</p>
            <p className="mt-1 text-sm text-gray-600">{t("quick_tunnel_long")}</p>
            <p className="mt-1 text-xs text-gray-500">{t("quick_tunnel_note")}</p>
          </button>
          <button
            onClick={() => setSelectedMode("cloudflare")}
            className={cn(
              "w-full rounded-lg border p-4 text-left",
              selectedMode === "cloudflare"
                ? "border-orange-500 bg-orange-50"
                : "border-gray-200 bg-white"
            )}
          >
            <p className="font-medium text-gray-900">{t("named_tunnel")}</p>
            <p className="mt-1 text-sm text-gray-600">{t("named_tunnel_long")}</p>
            <p className="mt-1 text-xs text-gray-500">{t("named_tunnel_note")}</p>
          </button>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => {
              if (selectedMode === "quick") {
                void handleConnect();
              } else {
                setStep("token");
              }
            }}
            disabled={status?.cloudflared_installed === false}
            title={
              status?.cloudflared_installed === false
                ? t("install_cloudflared_first", "Install cloudflared first")
                : undefined
            }
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {selectedMode === "quick" ? t("start_quick_tunnel") : t("setup_named_tunnel")}
          </button>
          <button
            type="button"
            onClick={() => openExternalUrl("https://one.dash.cloudflare.com/")}
            className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white hover:bg-orange-600"
          >
            {t("open_cloudflare_dashboard")}
          </button>
        </div>
      </div>
    </div>
  );
}

function SetupMainIntro({ data }: { data: SetupPageData }) {
  const { mobileMessage, status } = data;

  return (
    <>
      {mobileMessage && (
        <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          {mobileMessage}
        </div>
      )}
      <section className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="space-y-6">
          <MobileSetupSection data={data} />
        </div>
        <div className="space-y-6">
          <AiSettingsCard data={data} />
        </div>
      </section>
      <SetupSummaryCards data={data} />
      {status?.tunnel_active && <MobileOperationsCard data={data} />}
    </>
  );
}

function SetupTokenStep({ data }: { data: SetupPageData }) {
  const { t, token, setToken, error, status, handleConnect, setStep, mobileMessage } = data;

  return (
    <>
      {mobileMessage && (
        <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          {mobileMessage}
        </div>
      )}
      <div className="space-y-1 text-center">
        <h1 className="text-xl font-bold text-gray-900">{t("enter_tunnel_token")}</h1>
        <p className="text-sm text-gray-500">{t("tunnel_token_desc")}</p>
      </div>
      <div className="space-y-3 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
        <label className="block text-sm font-medium text-gray-700">{t("tunnel_token")}</label>
        <textarea
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="eyJhIjoixxxxxxx..."
          rows={4}
          className="w-full resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {error && <p className="text-sm text-red-600">{error}</p>}
        {status?.cloudflared_installed === false && (
          <p className="text-xs text-amber-700">
            {t(
              "source_requires_cloudflared",
              "If you are running from source, cloudflared may still need to be installed."
            )}
          </p>
        )}
        <p className="text-xs leading-5 text-gray-500">
          {t("token_ready_note", "Only tokens with completed Cloudflare setup can connect.")}
        </p>
      </div>
      <button
        onClick={() => void handleConnect()}
        disabled={!token.trim() || status?.cloudflared_installed === false}
        className="w-full rounded-lg bg-blue-600 px-4 py-2 font-medium text-white disabled:opacity-50"
      >
        {t("connect")}
      </button>
      <button
        onClick={() => setStep("intro")}
        className="w-full py-2 text-sm text-gray-400 hover:text-gray-600"
      >
        {t("back")}
      </button>
    </>
  );
}

function SetupDoneStep({ data }: { data: SetupPageData }) {
  const router = useRouter();
  const { t, selectedMode, tunnelUrl, mobileMessage, openedFromSettings } = data;

  return (
    <>
      {mobileMessage && (
        <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">
          {mobileMessage}
        </div>
      )}
      <div className="space-y-2 text-center">
        <div className="text-4xl">✓</div>
        <h1 className="text-xl font-bold text-gray-900">{t("connection_complete")}</h1>
      </div>
      <div className="space-y-2 rounded-2xl border border-green-200 bg-green-50 p-4">
        <p className="text-xs text-green-600">
          {selectedMode === "quick" ? t("quick_tunnel_label", "Quick Tunnel") : t("named_tunnel")}
        </p>
        <p className="text-sm font-medium text-green-700">{t("tunnel_url")}</p>
        <p className="break-all font-mono text-sm text-green-800">{tunnelUrl}</p>
        <p className="text-xs text-green-600">{t("open_remotely_desc")}</p>
      </div>
      <section className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="space-y-6">
          <MobileOperationsCard data={data} />
        </div>
        <div className="space-y-6">
          <AiSettingsCard data={data} />
        </div>
      </section>
      <SetupSummaryCards data={data} />
      <button
        onClick={() => router.push("/")}
        className="w-full rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700"
      >
        {openedFromSettings ? t("go_back", "Back") : t("start")}
      </button>
    </>
  );
}

export default function SetupPage() {
  const data = useSetupPageData();
  const { t, status, step } = data;

  return (
    <SetupShell
      title={t("setup_title")}
      description={t(
        "setup_overview_short",
        "Manage mobile access, AI, and permissions in one place."
      )}
      status={status}
    >
      {status?.cloudflared_installed === false && (
        <div className="space-y-2 rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <h2 className="text-sm font-semibold text-amber-900">
            {t("mobile_tool_missing_title", "Phone connection is not ready yet")}
          </h2>
          <p className="text-sm leading-6 text-amber-800">
            {t("missing_mobile_tool_desc", "This app could not find the phone connection tool.")}
          </p>
        </div>
      )}
      {step === "intro" && <SetupMainIntro data={data} />}
      {step === "token" && <SetupTokenStep data={data} />}
      {step === "connecting" && (
        <div className="space-y-4 rounded-3xl border border-gray-200 bg-white p-8 text-center shadow-sm">
          <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
          <p className="text-gray-600">{t("connecting_tunnel")}</p>
          <p className="text-sm text-gray-400">{t("up_to_20_seconds")}</p>
        </div>
      )}
      {step === "done" && <SetupDoneStep data={data} />}
    </SetupShell>
  );
}

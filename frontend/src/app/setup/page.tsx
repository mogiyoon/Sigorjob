"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import LanguageToggle from "@/components/LanguageToggle";
import { useLanguage } from "@/components/LanguageProvider";
import { openExternalUrl } from "@/lib/external";
import {
  authorizeConnection,
  callbackConnection,
  deleteCustomConnection,
  disconnectConnection,
  disconnectTunnel,
  getMcpPresets,
  getSetupStatus,
  installPlaywright,
  installMcpPreset,
  localApiFetch,
  sendTestMobileNotification,
  type ConnectionItem,
  type CustomConnectionRequest,
  type McpPresetItem,
  type PermissionItem,
  uninstallMcpPreset,
  upsertCustomConnection,
  updatePermission,
} from "@/lib/api";

type Step = "intro" | "token" | "connecting" | "done";
type TunnelMode = "none" | "quick" | "cloudflare";
type SetupStatus = {
  configured: boolean;
  tunnel_mode: TunnelMode;
  tunnel_active: boolean;
  tunnel_url: string | null;
  cloudflared_installed: boolean;
  cloudflared_path: string | null;
  tunnel_error: string | null;
  ai_configured: boolean;
  ai_verified: boolean;
  ai_validation_error: string | null;
  ai_verified_at: string | null;
  ai_storage_backend: "keychain" | "config";
  playwright: {
    installed: boolean;
    browsers_installed: boolean;
    install_command: string;
    browser_install_command: string;
  };
  connections: ConnectionItem[];
  permissions: PermissionItem[];
};

export default function SetupPage() {
  const router = useRouter();
  const { t } = useLanguage();
  const [openedFromSettings, setOpenedFromSettings] = useState(false);
  const [step, setStep] = useState<Step>("intro");
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [tunnelUrl, setTunnelUrl] = useState("");
  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [selectedMode, setSelectedMode] = useState<TunnelMode>("quick");
  const [apiKey, setApiKey] = useState("");
  const [aiSaving, setAiSaving] = useState(false);
  const [aiMessage, setAiMessage] = useState("");
  const [mobileMessage, setMobileMessage] = useState("");
  const [notificationTesting, setNotificationTesting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [showAiErrorDetails, setShowAiErrorDetails] = useState(false);
  const [customConnectionTitle, setCustomConnectionTitle] = useState("");
  const [customConnectionUrlTemplate, setCustomConnectionUrlTemplate] = useState("");
  const [customConnectionTitleTemplate, setCustomConnectionTitleTemplate] = useState("");
  const [customConnectionMessage, setCustomConnectionMessage] = useState("");
  const [customConnectionSaving, setCustomConnectionSaving] = useState(false);
  const [showConnectorAdvanced, setShowConnectorAdvanced] = useState(false);
  const [connectionMessage, setConnectionMessage] = useState("");
  const [connectingConnectionId, setConnectingConnectionId] = useState<string | null>(null);
  const [disconnectingConnectionId, setDisconnectingConnectionId] = useState<string | null>(null);
  const [mcpPresets, setMcpPresets] = useState<McpPresetItem[]>([]);
  const [mcpPresetMessage, setMcpPresetMessage] = useState("");
  const [mcpPresetAction, setMcpPresetAction] = useState<{
    presetId: string;
    type: "install" | "uninstall";
  } | null>(null);
  const [playwrightInstalling, setPlaywrightInstalling] = useState(false);
  const [playwrightMessage, setPlaywrightMessage] = useState("");

  const getConnectionBadgeClass = (connection: ConnectionItem) => {
    if (connection.verified) return "bg-green-100 text-green-700";
    if (connection.configured) return "bg-amber-100 text-amber-700";
    if (connection.available) return "bg-blue-100 text-blue-700";
    return "bg-gray-100 text-gray-600";
  };

  const getConnectionStatusLabel = (connection: ConnectionItem) => {
    if (connection.verified) return t("connected_short", "Connected");
    if (connection.configured) return t("needs_check_short", "Check");
    if (connection.status === "planned") return t("planned_short", "Planned");
    if (connection.available) return t("ready_short", "Ready");
    return t("not_set_short", "Not set");
  };

  const getConnectionActionHint = (connection: ConnectionItem) => {
    if (connection.verified) return t("connection_manage_hint", "Ready to use in tasks.");
    if (connection.configured) return t("connection_verify_hint", "Connected info exists, but it still needs to be checked.");
    if (connection.id === "gmail") return t("gmail_connect_hint", "Connect Gmail before asking Sigorjob to send real email.");
    if (connection.id === "google_calendar") return t("calendar_connect_hint", "Connect Calendar before asking Sigorjob to create real events.");
    if (connection.id === "mcp_runtime") return t("mcp_connect_hint", "This will become the shared base for external MCP tools.");
    return t("connection_connect_hint", "Connect this before using related actions.");
  };

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
      const data = (await getSetupStatus()) as SetupStatus;
      setStatus(data);
      if (data.tunnel_mode) {
        setSelectedMode(data.tunnel_mode);
      }
      if (data.tunnel_active && data.tunnel_url) {
        setTunnelUrl(data.tunnel_url);
        setStep("done");
      }
    } catch {
      // ignore initial status fetch failures
    }
  };

  const refreshMcpPresets = async () => {
    try {
      const presets = await getMcpPresets();
      setMcpPresets(presets);
    } catch {
      // ignore initial preset fetch failures
    }
  };

  const supportsOAuthConnection = (connection: ConnectionItem) =>
    connection.id === "google_calendar" ||
    connection.id === "gmail" ||
    connection.auth_type === "oauth" ||
    connection.auth_type === "oauth2";

  const isConnectionReady = (connection: ConnectionItem | undefined) =>
    Boolean(connection && (connection.verified || connection.configured || connection.status === "connected"));

  const pollConnectionStatus = async (connectionId: string, timeoutMs = 30000, intervalMs = 2000) => {
    const startedAt = Date.now();

    while (Date.now() - startedAt < timeoutMs) {
      const latest = (await getSetupStatus()) as SetupStatus;
      setStatus(latest);
      const matched = latest.connections.find((connection) => connection.id === connectionId);
      if (isConnectionReady(matched)) {
        return true;
      }
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }

    return false;
  };

  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      setOpenedFromSettings(params.get("source") === "settings");
    }
    refreshStatus();
    refreshMcpPresets();
    const interval = setInterval(refreshStatus, 3000);
    const presetInterval = setInterval(refreshMcpPresets, 3000);
    return () => {
      clearInterval(interval);
      clearInterval(presetInterval);
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const params = new URLSearchParams(window.location.search);
    const state = params.get("state");
    const code = params.get("code");
    if (!state || !code) return;

    const connectionId = state.split(":")[0]?.trim();
    if (!connectionId) return;

    let cancelled = false;

    const handleOAuthCallback = async () => {
      setConnectingConnectionId(connectionId);
      setConnectionMessage("");
      try {
        await callbackConnection(connectionId, { code, state });
        if (cancelled) return;
        await pollConnectionStatus(connectionId);
        if (cancelled) return;
        const nextParams = new URLSearchParams(window.location.search);
        nextParams.delete("code");
        nextParams.delete("state");
        const nextQuery = nextParams.toString();
        window.history.replaceState(
          {},
          "",
          `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}`
        );
      } catch {
        if (!cancelled) {
          setConnectionMessage(
            t("connection_callback_failed", "Could not finish the connection. Try again.")
          );
        }
      } finally {
        if (!cancelled) {
          setConnectingConnectionId((current) => (current === connectionId ? null : current));
        }
      }
    };

    void handleOAuthCallback();

    return () => {
      cancelled = true;
    };
  }, [t]);

  const waitForTunnelReady = async (timeoutMs = 12000) => {
    const startedAt = Date.now();
    while (Date.now() - startedAt < timeoutMs) {
      const latest = (await getSetupStatus()) as SetupStatus;
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
          ? await localApiFetch("/setup/quick", {
              method: "POST",
            })
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
            : getFriendlyAiError(data.validation_error) || t("ai_key_saved_unverified", "The AI key is saved, but real AI access has not been confirmed yet.")
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
          getFriendlyAiError(data.validation_error ?? data.error) || t("ai_verify_failed_short", "Could not verify AI access.")
        );
      }
      await refreshStatus();
    } catch {
      setAiMessage(t("ai_verify_failed_short", "Could not verify AI access."));
    } finally {
      setAiSaving(false);
    }
  };

  const handlePermissionToggle = async (permission: PermissionItem) => {
    try {
      await updatePermission(permission.id, !permission.granted);
      await refreshStatus();
    } catch {
      setAiMessage(t("permission_update_failed", "Could not update the permission."));
    }
  };

  const handleTestNotification = async () => {
    setNotificationTesting(true);
    setMobileMessage("");
    try {
      await sendTestMobileNotification({
        title: "Sigorjob test",
        body: "If your phone is connected and the app is open, you should see this in a few seconds.",
      });
      setMobileMessage(t("test_notification_sent", "A test notification has been queued. Keep the phone app open and wait a few seconds."));
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

  const handleAuthorizeConnection = async (connectionId: string) => {
    setConnectingConnectionId(connectionId);
    setConnectionMessage("");
    try {
      const { auth_url } = await authorizeConnection(connectionId);
      await openExternalUrl(auth_url);
      const connected = await pollConnectionStatus(connectionId);
      if (!connected) {
        setConnectionMessage(
          t(
            "connection_pending_message",
            "Waiting for the connection to finish. Complete the sign-in window, then the status will refresh here."
          )
        );
      }
    } catch {
      setConnectionMessage(t("connection_authorize_failed", "Could not start the connection flow."));
    } finally {
      setConnectingConnectionId((current) => (current === connectionId ? null : current));
    }
  };

  const handleDisconnectConnection = async (connectionId: string) => {
    setDisconnectingConnectionId(connectionId);
    setConnectionMessage("");
    try {
      await disconnectConnection(connectionId);
      await refreshStatus();
    } catch {
      setConnectionMessage(t("connection_disconnect_failed", "Could not disconnect the service."));
    } finally {
      setDisconnectingConnectionId((current) => (current === connectionId ? null : current));
    }
  };

  const handleInstallMcpPreset = async (presetId: string) => {
    setMcpPresetAction({ presetId, type: "install" });
    setMcpPresetMessage("");
    try {
      const data = await installMcpPreset(presetId);
      if (!data.success) {
        setMcpPresetMessage(
          data.error || t("mcp_preset_install_failed", "Could not install the MCP preset.")
        );
        return;
      }
      await refreshMcpPresets();
    } catch {
      setMcpPresetMessage(
        t("mcp_preset_install_failed", "Could not install the MCP preset.")
      );
    } finally {
      setMcpPresetAction((current) =>
        current?.presetId === presetId && current.type === "install" ? null : current
      );
    }
  };

  const handleUninstallMcpPreset = async (presetId: string) => {
    setMcpPresetAction({ presetId, type: "uninstall" });
    setMcpPresetMessage("");
    try {
      const data = await uninstallMcpPreset(presetId);
      if (!data.success) {
        setMcpPresetMessage(
          data.error || t("mcp_preset_uninstall_failed", "Could not uninstall the MCP preset.")
        );
        return;
      }
      await refreshMcpPresets();
    } catch {
      setMcpPresetMessage(
        t("mcp_preset_uninstall_failed", "Could not uninstall the MCP preset.")
      );
    } finally {
      setMcpPresetAction((current) =>
        current?.presetId === presetId && current.type === "uninstall" ? null : current
      );
    }
  };

  const handleInstallPlaywright = async () => {
    setPlaywrightInstalling(true);
    setPlaywrightMessage("");
    try {
      const data = await installPlaywright();
      if (!data.success) {
        setPlaywrightMessage(
          data.error || t("playwright_install_failed", "Could not install Playwright.")
        );
        return;
      }
      setPlaywrightMessage(
        t("playwright_install_success", "Playwright installation finished.")
      );
      await refreshStatus();
    } catch {
      setPlaywrightMessage(
        t("playwright_install_failed", "Could not install Playwright.")
      );
    } finally {
      setPlaywrightInstalling(false);
    }
  };

  const connectedExternalConnections = (status?.connections ?? []).filter(
    (connection) => connection.kind === "external" && (connection.verified || connection.configured)
  );

  const availableExternalConnections = (status?.connections ?? []).filter(
    (connection) => connection.kind === "external" && !connection.verified && !connection.configured
  );
  const customExternalConnections = (status?.connections ?? []).filter(
    (connection) => connection.kind === "external" && connection.driver_id === "template_connector"
  );

  const groupedPermissions = (status?.permissions ?? []).reduce<Record<string, PermissionItem[]>>((acc, permission) => {
    const key = permission.group || "advanced";
    acc[key] = [...(acc[key] ?? []), permission];
    return acc;
  }, {});

  const renderPermissionRow = (permission: PermissionItem) => (
    <div
      key={permission.id}
      className="rounded-2xl border border-gray-200 bg-white p-4 flex items-start justify-between gap-4"
    >
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium text-gray-900">{permission.title}</p>
          {permission.risk === "high" && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800">
              {t("risk_high", "Caution")}
            </span>
          )}
        </div>
        <p className="text-xs text-gray-600 leading-5">{permission.description}</p>
        <p className="text-xs text-gray-500">{t("storage_location")}: {permission.source}</p>
      </div>
      <button
        onClick={() => handlePermissionToggle(permission)}
        className={`rounded-full px-3 py-1.5 text-xs font-medium ${
          permission.granted
            ? "bg-green-100 text-green-700"
            : "bg-gray-200 text-gray-700"
        }`}
      >
        {permission.granted ? t("permission_allowed") : t("permission_not_allowed")}
      </button>
    </div>
  );

  const buildCustomConnectionId = (title: string) =>
    title
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9가-힣]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 40) || "custom_connector";

  const handleSaveCustomConnection = async () => {
    if (!customConnectionTitle.trim() || !customConnectionUrlTemplate.trim()) {
      setCustomConnectionMessage(t("custom_connector_required_fields", "Enter a name and URL template first."));
      return;
    }

    setCustomConnectionSaving(true);
    setCustomConnectionMessage("");
    try {
      const connectionId = buildCustomConnectionId(customConnectionTitle);
      const payload: CustomConnectionRequest = {
        connection_id: connectionId,
        title: customConnectionTitle.trim(),
        description: t(
          "custom_connector_default_description",
          "User-defined connector added from the settings screen."
        ),
        provider: "custom",
        auth_type: "manual",
        driver_id: "template_connector",
        capabilities: ["create_calendar_event"],
        capability_permissions: {
          create_calendar_event: ["calendar_event_creation"],
        },
        configured: true,
        verified: true,
        available: true,
        metadata: {
          templates: {
            create_calendar_event: {
              url_template: customConnectionUrlTemplate.trim(),
              title_template: customConnectionTitleTemplate.trim() || "{title} 일정 만들기",
            },
          },
        },
      };
      const data = await upsertCustomConnection(payload);
      if (!data.success) {
        setCustomConnectionMessage(data.error || t("custom_connector_save_failed", "Could not save the custom connector."));
        return;
      }
      setCustomConnectionMessage(t("custom_connector_saved", "Custom connector saved."));
      setCustomConnectionTitle("");
      setCustomConnectionUrlTemplate("");
      setCustomConnectionTitleTemplate("");
      await refreshStatus();
    } catch {
      setCustomConnectionMessage(t("custom_connector_save_failed", "Could not save the custom connector."));
    } finally {
      setCustomConnectionSaving(false);
    }
  };

  const handleDeleteCustomConnection = async (connectionId: string) => {
    setCustomConnectionSaving(true);
    setCustomConnectionMessage("");
    try {
      const data = await deleteCustomConnection(connectionId);
      if (!data.success) {
        setCustomConnectionMessage(data.error || t("custom_connector_delete_failed", "Could not remove the custom connector."));
        return;
      }
      setCustomConnectionMessage(t("custom_connector_deleted", "Custom connector removed."));
      await refreshStatus();
    } catch {
      setCustomConnectionMessage(t("custom_connector_delete_failed", "Could not remove the custom connector."));
    } finally {
      setCustomConnectionSaving(false);
    }
  };

  const aiSettingsCard = (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 space-y-4 shadow-sm">
      <div className="space-y-1">
        <h2 className="font-semibold text-gray-900">{t("ai_fallback_setup")}</h2>
        <p className="text-sm text-gray-600">
          {t("ai_setup_short_desc", "Set up AI so it can continue tasks when needed.")}
        </p>
      </div>
      <div className="rounded-2xl border border-gray-100 bg-gray-50 p-4 space-y-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-gray-900">{t("anthropic_api_key")}</p>
            <p className="text-xs text-gray-500">
              {t("ai_usage_desc")}
            </p>
            <p className="text-xs text-gray-500">
              {t("storage_location")}: {status?.ai_storage_backend === "keychain" ? t("keychain") : t("local_secure_config")}
            </p>
          </div>
          <span
            className={`rounded-full px-2 py-1 text-xs font-medium ${
              status?.ai_verified
                ? "bg-green-100 text-green-700"
                : status?.ai_configured
                  ? "bg-amber-100 text-amber-700"
                : "bg-gray-100 text-gray-600"
            }`}
          >
            {status?.ai_verified ? t("configured") : status?.ai_configured ? t("ai_ready", "Ready") : t("not_set")}
          </span>
        </div>
        {status?.ai_configured && !status.ai_verified && (
          <div className="space-y-2">
            <p className="text-xs text-amber-700">
              {getFriendlyAiError(status.ai_validation_error) || "The key is saved, but real AI access is not confirmed yet."}
            </p>
            {status.ai_validation_error && (
              <div className="space-y-2">
                <button
                  type="button"
                  onClick={() => setShowAiErrorDetails((prev) => !prev)}
                  className="text-xs font-medium text-amber-800 underline underline-offset-2"
                >
                  {showAiErrorDetails
                    ? t("hide_ai_error_details", "Hide technical details")
                    : t("show_ai_error_details", "Show technical details")}
                </button>
                {showAiErrorDetails && (
                  <pre className="overflow-x-auto rounded-lg bg-amber-100 p-3 text-xs leading-5 text-amber-900 whitespace-pre-wrap break-words">
                    {status.ai_validation_error}
                  </pre>
                )}
              </div>
            )}
          </div>
        )}
        {status?.ai_verified && (
          <p className="text-xs text-green-700">
            {t("ai_verified_desc", "Real AI access has been confirmed.")}
          </p>
        )}
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="sk-ant-..."
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {aiMessage && <p className="text-sm text-gray-600">{aiMessage}</p>}
        <div className="flex gap-2">
          <button
            onClick={handleSaveAiKey}
            disabled={aiSaving || !apiKey.trim()}
            className="flex-1 rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {aiSaving ? t("saving") : t("save_ai_key")}
          </button>
          {status?.ai_configured && (
            <button
              onClick={handleVerifyAiKey}
              disabled={aiSaving}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 disabled:opacity-50"
            >
              {t("verify_connection", "Check AI access")}
            </button>
          )}
          {status?.ai_configured && (
            <button
              onClick={handleRemoveAiKey}
              disabled={aiSaving}
              className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 disabled:opacity-50"
            >
              {t("remove")}
            </button>
          )}
        </div>
      </div>
      <div className="rounded-2xl border border-gray-100 bg-white p-4 space-y-3">
        <div className="space-y-1">
          <p className="text-sm font-medium text-gray-900">{t("api_key_guide")}</p>
          <p className="text-xs text-gray-500 leading-5">
            {t("api_key_guide_short_desc", "Use these links to see where keys are created.")}
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
                onClick={() => openExternalUrl("https://docs.anthropic.com/en/api/getting-started")}
                className="text-sm font-medium text-blue-700 underline underline-offset-2"
              >
                {t("issuance_guide")}
              </button>
            </div>
            <p className="mt-2 text-xs text-blue-800 leading-5">
              {t("anthropic_issue_desc")}
            </p>
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
            <p className="mt-2 text-xs text-gray-700 leading-5">
              {t("openai_issue_desc")}
            </p>
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
            <p className="mt-2 text-xs text-gray-700 leading-5">
              {t("gemini_issue_desc")}
            </p>
          </div>
        </div>
      </div>
    </div>
  );

  const permissionsCard = (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 space-y-4 shadow-sm">
      <div className="space-y-1">
        <h2 className="font-semibold text-gray-900">{t("permissions_title")}</h2>
        <p className="text-sm text-gray-600">{t("permissions_short_desc", "Turn sensitive features on or off here.")}</p>
      </div>
      {groupedPermissions.core_access && (
        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 space-y-3">
          <div className="space-y-1">
            <p className="text-sm font-medium text-gray-900">{t("core_permissions_title", "Core access")}</p>
            <p className="text-xs text-gray-600 leading-5">
              {t("core_permissions_desc", "These switches control the main Sigorjob experiences people notice first.")}
            </p>
          </div>
          <div className="space-y-3">
            {groupedPermissions.core_access.map(renderPermissionRow)}
          </div>
        </div>
      )}
      {groupedPermissions.service_extensions && (
        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 space-y-3">
          <div className="space-y-1">
            <p className="text-sm font-medium text-gray-900">{t("service_permissions_title", "Service extensions")}</p>
            <p className="text-xs text-gray-600 leading-5">
              {t("service_permissions_desc", "Use these when Gmail, Calendar, or future MCP-based add-ons should be available.")}
            </p>
          </div>
          <div className="space-y-3">
            {groupedPermissions.service_extensions
              .filter((permission) => !permission.advanced)
              .map(renderPermissionRow)}
          </div>
        </div>
      )}
      {(status?.permissions ?? []).some((permission) => permission.risk === "high") && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 space-y-2">
          <p className="text-sm font-medium text-amber-900">{t("sensitive_permissions_title", "Sensitive permissions")}</p>
          <p className="text-xs text-amber-800 leading-5">
            {t("sensitive_permissions_desc", "Manage payment, purchase, and external service actions separately here.")}
          </p>
          <div className="space-y-3">
            {(status?.permissions ?? [])
              .filter((permission) => permission.risk === "high")
              .map(renderPermissionRow)}
          </div>
        </div>
      )}
      {((groupedPermissions.service_extensions ?? []).some((permission) => permission.advanced) ||
        (groupedPermissions.advanced ?? []).length > 0) && (
        <div className="space-y-3 rounded-2xl border border-gray-200 bg-gray-50 p-4">
          <div className="space-y-1">
            <p className="text-sm font-medium text-gray-900">{t("advanced_permissions_title", "Advanced permissions")}</p>
            <p className="text-xs text-gray-600 leading-5">
              {t("advanced_permissions_desc", "Keep rarely used or developer-oriented permissions tucked away here.")}
            </p>
          </div>
          <div className="space-y-3">
            {(groupedPermissions.service_extensions ?? [])
              .filter((permission) => permission.advanced)
              .map(renderPermissionRow)}
            {(groupedPermissions.advanced ?? []).map(renderPermissionRow)}
          </div>
        </div>
      )}
    </div>
  );

  const externalConnectionsCard = (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 space-y-4 shadow-sm">
      <div className="space-y-1">
        <h2 className="font-semibold text-gray-900">
          {t("external_connections_title", "External connections")}
        </h2>
        <p className="text-sm text-gray-600">
          {t(
            "external_connections_desc",
            "Use one shared place for Gmail, Calendar, and future MCP tools."
          )}
        </p>
        <p className="text-xs text-gray-500 leading-5">
          {t(
            "external_connections_separate_hint",
            "This section only shows whether a service is connected. Actual permission switches live in the permission area below."
          )}
        </p>
      </div>
      {connectionMessage && (
        <p className="text-sm text-gray-600">{connectionMessage}</p>
      )}
      {connectedExternalConnections.length > 0 && (
        <div className="space-y-3">
          <div className="space-y-1">
            <p className="text-sm font-medium text-gray-900">
              {t("connected_services_title", "Connected or ready")}
            </p>
            <p className="text-xs text-gray-500 leading-5">
              {t("connected_services_desc", "These services already have saved connection information or are ready to use.")}
            </p>
          </div>
          {connectedExternalConnections.map((connection) => (
            <div
              key={connection.id}
              className="rounded-2xl border border-gray-200 bg-gray-50 p-4 space-y-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-gray-900">{connection.title}</p>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${getConnectionBadgeClass(connection)}`}
                    >
                      {getConnectionStatusLabel(connection)}
                    </span>
                  </div>
                  <p className="text-xs leading-5 text-gray-600">{connection.description}</p>
                </div>
                <span className="rounded-full bg-white px-2 py-1 text-[11px] font-medium uppercase tracking-wide text-gray-500 border border-gray-200">
                  {connection.provider}
                </span>
              </div>
              <p className="text-xs leading-5 text-gray-500">{getConnectionActionHint(connection)}</p>
              <div className="rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs text-gray-500">
                {t(
                  "connection_permissions_separate_hint",
                  "If you want to allow real actions with this service, turn the related permission on in the permission section below."
                )}
              </div>
              {supportsOAuthConnection(connection) && (
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => handleDisconnectConnection(connection.id)}
                    disabled={disconnectingConnectionId === connection.id}
                    className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-700 disabled:opacity-50"
                  >
                    {disconnectingConnectionId === connection.id
                      ? t("disconnecting_short", "Disconnecting...")
                      : t("disconnect_service", "Disconnect")}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {availableExternalConnections.length > 0 && (
        <div className="space-y-3">
          <div className="space-y-1">
            <p className="text-sm font-medium text-gray-900">
              {t("available_services_title", "Available to connect")}
            </p>
            <p className="text-xs text-gray-500 leading-5">
              {t("available_services_desc", "These are not connected yet. Once connection setup exists, they will move into the ready section above.")}
            </p>
          </div>
          {availableExternalConnections.map((connection) => (
            <div
              key={connection.id}
              className="rounded-2xl border border-dashed border-gray-200 bg-white p-4 space-y-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-gray-900">{connection.title}</p>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${getConnectionBadgeClass(connection)}`}
                    >
                      {getConnectionStatusLabel(connection)}
                    </span>
                  </div>
                  <p className="text-xs leading-5 text-gray-600">{connection.description}</p>
                </div>
                <span className="rounded-full bg-gray-50 px-2 py-1 text-[11px] font-medium uppercase tracking-wide text-gray-500 border border-gray-200">
                  {connection.provider}
                </span>
              </div>
              <p className="text-xs leading-5 text-gray-500">{getConnectionActionHint(connection)}</p>
              {supportsOAuthConnection(connection) && (
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() => handleAuthorizeConnection(connection.id)}
                    disabled={connectingConnectionId === connection.id}
                    className="inline-flex items-center gap-2 rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                  >
                    {connectingConnectionId === connection.id && (
                      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                    )}
                    {connectingConnectionId === connection.id
                      ? t("connecting_oauth", "Connecting...")
                      : t("connect_service", "Connect")}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 space-y-3">
        <div className="space-y-1">
          <p className="text-sm font-medium text-gray-900">{t("custom_connectors_title", "Custom connectors")}</p>
          <p className="text-xs text-gray-600 leading-5">
            {t(
              "custom_connectors_desc",
              "Add shared connectors with capabilities and URL templates instead of building one-off service flows."
            )}
          </p>
        </div>
        <div className="grid gap-3">
          <input
            value={customConnectionTitle}
            onChange={(e) => setCustomConnectionTitle(e.target.value)}
            placeholder={t("custom_connector_title_placeholder", "Example: Team calendar")}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
          <input
            value={customConnectionUrlTemplate}
            onChange={(e) => setCustomConnectionUrlTemplate(e.target.value)}
            placeholder={t("custom_connector_url_placeholder", "URL template, e.g. https://calendar.example.com/new?title={title}&dates={dates}")}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
          />
        </div>
        <button
          type="button"
          onClick={() => setShowConnectorAdvanced((prev) => !prev)}
          className="w-fit rounded-full border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700"
        >
          {showConnectorAdvanced ? t("hide_connector_advanced", "Hide advanced fields") : t("show_connector_advanced", "Show advanced fields")}
        </button>
        {showConnectorAdvanced && (
          <div className="grid gap-3">
            <input
              value={customConnectionTitleTemplate}
              onChange={(e) => setCustomConnectionTitleTemplate(e.target.value)}
              placeholder={t("custom_connector_title_template_placeholder", "Title template, e.g. {title} schedule")}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </div>
        )}
        <div className="rounded-xl border border-blue-100 bg-blue-50 px-3 py-2 text-xs text-blue-800">
          {t(
            "custom_connector_hint",
            "The first UI only supports the create_calendar_event capability. Use placeholders like {title}, {details}, and {dates}."
          )}
        </div>
        {customConnectionMessage && <p className="text-xs text-gray-600">{customConnectionMessage}</p>}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={handleSaveCustomConnection}
            disabled={customConnectionSaving}
            className="rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {customConnectionSaving ? t("saving") : t("save_custom_connector", "Save connector")}
          </button>
        </div>
        {customExternalConnections.length > 0 && (
          <div className="space-y-2">
            {customExternalConnections.map((connection) => (
              <div key={connection.id} className="flex items-center justify-between gap-3 rounded-xl border border-gray-200 bg-white px-3 py-3">
                <div className="space-y-1">
                  <p className="text-sm font-medium text-gray-900">{connection.title}</p>
                  <p className="text-xs text-gray-500">{connection.id} · {connection.provider}</p>
                </div>
                <button
                  type="button"
                  onClick={() => handleDeleteCustomConnection(connection.id)}
                  disabled={customConnectionSaving}
                  className="rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-700 disabled:opacity-50"
                >
                  {t("remove")}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  const mcpPresetsCard = (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 space-y-4 shadow-sm">
      <div className="space-y-1">
        <h2 className="font-semibold text-gray-900">
          {t("mcp_presets_title", "MCP Presets")}
        </h2>
        <p className="text-sm text-gray-600">
          {t(
            "mcp_presets_desc",
            "Install or remove ready-made MCP bundles with one click."
          )}
        </p>
      </div>
      {mcpPresetMessage && (
        <p className="text-sm text-gray-600">{mcpPresetMessage}</p>
      )}
      {mcpPresets.length > 0 ? (
        <div className="space-y-3">
          {mcpPresets.map((preset) => {
            const isInstalling =
              mcpPresetAction?.presetId === preset.id && mcpPresetAction.type === "install";
            const isUninstalling =
              mcpPresetAction?.presetId === preset.id && mcpPresetAction.type === "uninstall";

            return (
              <div
                key={preset.id}
                className="rounded-2xl border border-gray-200 bg-gray-50 p-4 space-y-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-gray-900">{preset.name}</p>
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                          preset.installed
                            ? "bg-green-100 text-green-700"
                            : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {preset.installed
                          ? t("installed_short", "Installed")
                          : t("not_installed_short", "Not installed")}
                      </span>
                    </div>
                    <p className="text-xs leading-5 text-gray-600">{preset.description}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() =>
                      preset.installed
                        ? handleUninstallMcpPreset(preset.id)
                        : handleInstallMcpPreset(preset.id)
                    }
                    disabled={isInstalling || isUninstalling}
                    className={`rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 ${
                      preset.installed
                        ? "border border-red-200 text-red-700"
                        : "bg-gray-900 text-white"
                    }`}
                  >
                    {isInstalling
                      ? t("installing_short", "Installing...")
                      : isUninstalling
                        ? t("uninstalling_short", "Uninstalling...")
                        : preset.installed
                          ? t("uninstall", "Uninstall")
                          : t("install", "Install")}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 p-4 text-sm text-gray-500">
          {t("mcp_presets_empty", "No MCP presets are available right now.")}
        </div>
      )}
    </div>
  );

  const toolsCard = (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 space-y-4 shadow-sm">
      <div className="space-y-1">
        <h2 className="font-semibold text-gray-900">{t("tools_title", "Tools")}</h2>
        <p className="text-sm text-gray-600">
          {t("tools_desc", "Install local tools required for browser automation and similar tasks.")}
        </p>
      </div>
      <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <p className="text-sm font-medium text-gray-900">Playwright</p>
              <span
                className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                  status?.playwright.installed
                    ? "bg-green-100 text-green-700"
                    : "bg-gray-100 text-gray-600"
                }`}
              >
                {status?.playwright.installed
                  ? t("installed_short", "Installed")
                  : t("not_installed_short", "Not installed")}
              </span>
            </div>
            <p className="text-xs leading-5 text-gray-600">
              {t(
                "playwright_desc",
                "Required for browser automation tasks that open and control Chromium."
              )}
            </p>
          </div>
          {!status?.playwright.installed && (
            <button
              type="button"
              onClick={handleInstallPlaywright}
              disabled={playwrightInstalling}
              className="rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {playwrightInstalling
                ? t("installing_short", "Installing...")
                : t("install", "Install")}
            </button>
          )}
        </div>
        {!status?.playwright.installed && (
          <p className="text-xs text-amber-700 leading-5">
            {t(
              "playwright_install_notice",
              "Installing Playwright may take a few minutes because Chromium also needs to be downloaded."
            )}
          </p>
        )}
        {playwrightMessage && <p className="text-sm text-gray-600">{playwrightMessage}</p>}
      </div>
    </div>
  );

  const mobileOperationsCard = (
    <div className="rounded-2xl border border-gray-200 bg-white p-4 space-y-3 shadow-sm">
      <div className="space-y-1">
        <p className="text-sm font-semibold text-gray-900">
          {t("mobile_operations", "Mobile actions")}
        </p>
        <p className="text-xs text-gray-600 leading-5">
          {t("mobile_operations_short_desc", "Send a test notification or disconnect and start again.")}
        </p>
      </div>
      <div className="flex gap-2">
        <button
          onClick={handleTestNotification}
          disabled={notificationTesting}
          className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 disabled:opacity-50"
        >
          {notificationTesting ? t("sending", "Sending...") : t("send_test_notification", "Send test notification")}
        </button>
        <button
          onClick={handleDisconnectTunnel}
          disabled={disconnecting}
          className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-700 disabled:opacity-50"
        >
          {disconnecting ? t("disconnecting_short", "Disconnecting...") : t("disconnect_mobile_connection", "Disconnect phone connection")}
        </button>
      </div>
    </div>
  );

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
              <h1 className="text-2xl font-semibold tracking-tight text-gray-950">{t("setup_title")}</h1>
              <p className="text-sm text-gray-500">{t("setup_overview_short", "Manage mobile access, AI, and permissions in one place.")}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  status?.tunnel_active
                    ? "bg-emerald-50 text-emerald-800"
                    : "bg-slate-100 text-slate-700"
                }`}
              >
                {t("mobile_connection", "Mobile")}: {status?.tunnel_active ? t("connected_short", "Connected") : t("disconnected_short", "Off")}
              </span>
              <span
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  status?.ai_verified
                    ? "bg-violet-50 text-violet-800"
                    : status?.ai_configured
                      ? "bg-amber-50 text-amber-800"
                      : "bg-slate-100 text-slate-700"
                }`}
              >
                AI: {status?.ai_verified ? t("connected_short", "Connected") : status?.ai_configured ? t("ready_short", "Ready") : t("not_set_short", "Not set")}
              </span>
            </div>
          </div>
        </section>
        {status?.cloudflared_installed === false && (
          <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 space-y-2">
            <h2 className="text-sm font-semibold text-amber-900">
              {t("mobile_tool_missing_title", "Phone connection is not ready yet")}
            </h2>
            <p className="text-sm text-amber-800 leading-6">
              {t("missing_mobile_tool_desc", "This app could not find the phone connection tool.")}
            </p>
          </div>
        )}

        {step === "intro" && (
          <>
            {mobileMessage && (
              <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">
                {mobileMessage}
              </div>
            )}
            <section className="grid gap-6 xl:grid-cols-[1.08fr_0.92fr]">
              <div className="space-y-6">
                <div className="bg-white border border-gray-200 rounded-2xl p-5 space-y-4 shadow-sm">
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
                        : t("mobile_setup_status_idle", "Press the button once and wait a few seconds while the connection opens.")}
                  </div>
                  <div className="space-y-3">
                    <button
                      onClick={() => setSelectedMode("quick")}
                      className={`w-full rounded-lg border p-4 text-left ${
                        selectedMode === "quick"
                          ? "border-blue-500 bg-blue-50"
                          : "border-gray-200 bg-white"
                      }`}
                    >
                      <p className="font-medium text-gray-900">{t("quick_tunnel")}</p>
                      <p className="mt-1 text-sm text-gray-600">
                        {t("quick_tunnel_long")}
                      </p>
                      <p className="mt-1 text-xs text-gray-500">
                        {t("quick_tunnel_note")}
                      </p>
                    </button>
                    <button
                      onClick={() => setSelectedMode("cloudflare")}
                      className={`w-full rounded-lg border p-4 text-left ${
                        selectedMode === "cloudflare"
                          ? "border-orange-500 bg-orange-50"
                          : "border-gray-200 bg-white"
                      }`}
                    >
                      <p className="font-medium text-gray-900">{t("named_tunnel")}</p>
                      <p className="mt-1 text-sm text-gray-600">
                        {t("named_tunnel_long")}
                      </p>
                      <p className="mt-1 text-xs text-gray-500">
                        {t("named_tunnel_note")}
                      </p>
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    <button
                      onClick={() => {
                        setError("");
                        if (selectedMode === "quick") {
                          handleConnect();
                        } else {
                          setStep("token");
                        }
                      }}
                      disabled={status?.cloudflared_installed === false}
                      title={
                        status?.cloudflared_installed === false
                          ? "Install cloudflared first"
                          : undefined
                      }
                      className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
                    >
                      {selectedMode === "quick"
                        ? t("start_quick_tunnel")
                        : t("setup_named_tunnel")}
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

              <div className="space-y-6">
                {aiSettingsCard}
                {toolsCard}
                {externalConnectionsCard}
                {mcpPresetsCard}
                {permissionsCard}
              </div>
            </section>
          </>
        )}

        {step === "token" && (
          <>
            {mobileMessage && (
              <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">
                {mobileMessage}
              </div>
            )}
            <div className="text-center space-y-1">
              <h1 className="text-xl font-bold text-gray-900">{t("enter_tunnel_token")}</h1>
              <p className="text-sm text-gray-500">{t("tunnel_token_desc")}</p>
            </div>
            <div className="bg-white border border-gray-200 rounded-2xl p-4 space-y-3 shadow-sm">
              <label className="block text-sm font-medium text-gray-700">
                {t("tunnel_token")}
              </label>
              <textarea
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="eyJhIjoixxxxxxx..."
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
              />
              {error && (
                <p className="text-sm text-red-600">{error}</p>
              )}
              {status?.cloudflared_installed === false && (
                <p className="text-xs text-amber-700">
                  {t("source_requires_cloudflared", "If you are running from source, cloudflared may still need to be installed.")}
                </p>
              )}
              <p className="text-xs text-gray-500 leading-5">{t("token_ready_note", "Only tokens with completed Cloudflare setup can connect.")}</p>
            </div>
            {permissionsCard}
            <button
              onClick={handleConnect}
              disabled={!token.trim() || status?.cloudflared_installed === false}
              className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg font-medium"
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
        )}

        {step === "connecting" && (
          <div className="rounded-3xl border border-gray-200 bg-white p-8 text-center space-y-4 shadow-sm">
            <div className="animate-spin w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full mx-auto" />
            <p className="text-gray-600">{t("connecting_tunnel")}</p>
            <p className="text-sm text-gray-400">{t("up_to_20_seconds")}</p>
          </div>
        )}

        {step === "done" && (
          <>
            {mobileMessage && (
              <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">
                {mobileMessage}
              </div>
            )}
            <div className="text-center space-y-2">
              <div className="text-4xl">✓</div>
              <h1 className="text-xl font-bold text-gray-900">{t("connection_complete")}</h1>
            </div>
            <div className="bg-green-50 border border-green-200 rounded-2xl p-4 space-y-2">
              <p className="text-xs text-green-600">
                {selectedMode === "quick" ? "Quick Tunnel" : t("named_tunnel")}
              </p>
              <p className="text-sm text-green-700 font-medium">{t("tunnel_url")}</p>
              <p className="font-mono text-sm text-green-800 break-all">{tunnelUrl}</p>
              <p className="text-xs text-green-600">
                {t("open_remotely_desc")}
              </p>
            </div>
            <section className="grid gap-6 xl:grid-cols-[1.08fr_0.92fr]">
              <div className="space-y-6">
                {mobileOperationsCard}
              </div>
              <div className="space-y-6">
                {aiSettingsCard}
                {toolsCard}
                {externalConnectionsCard}
                {mcpPresetsCard}
                {permissionsCard}
              </div>
            </section>
            <button
              onClick={() => router.push("/")}
              className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium"
            >
              {openedFromSettings ? t("go_back", "Back") : t("start")}
            </button>
          </>
        )}

      </div>
    </main>
  );
}

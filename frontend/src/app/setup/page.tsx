"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import LanguageToggle from "@/components/LanguageToggle";
import { useLanguage } from "@/components/LanguageProvider";
import {
  disconnectTunnel,
  getSetupStatus,
  localApiFetch,
  sendTestMobileNotification,
  type PermissionItem,
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
  permissions: PermissionItem[];
};

export default function SetupPage() {
  const router = useRouter();
  const { t } = useLanguage();
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
        "Anthropic API 크레딧이 부족합니다. Console의 Plans & Billing에서 크레딧을 충전한 뒤 다시 연결 확인을 눌러주세요."
      );
    }
    if (normalized.includes("invalid x-api-key") || normalized.includes("authentication")) {
      return t(
        "ai_auth_failed",
        "Anthropic API key를 확인해주세요. 키가 잘못되었거나 더 이상 유효하지 않을 수 있습니다."
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
        "Anthropic API에 연결하지 못했습니다. 네트워크 상태를 확인한 뒤 다시 시도해주세요."
      );
    }
    return t(
      "ai_verify_failed_generic",
      "AI 연결 검증에 실패했습니다. 상세 오류를 확인한 뒤 다시 시도해주세요."
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

  useEffect(() => {
    refreshStatus();
  }, []);

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
        setError(data.error ?? "연결에 실패했습니다. 설정을 확인해주세요.");
        setStep(selectedMode === "cloudflare" ? "token" : "intro");
      }
    } catch {
      setError("백엔드에 연결할 수 없습니다. 앱이 실행 중인지 확인해주세요.");
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
            ? "AI key saved and verified successfully."
            : getFriendlyAiError(data.validation_error) || "AI key was saved, but the live connection could not be verified."
        );
        await refreshStatus();
      } else {
        setAiMessage(getFriendlyAiError(data.error) || "Failed to save AI key.");
      }
    } catch {
      setAiMessage("Failed to save AI key.");
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
        setAiMessage("Saved AI key was removed.");
        await refreshStatus();
      } else {
        setAiMessage("Failed to remove AI key.");
      }
    } catch {
      setAiMessage("Failed to remove AI key.");
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
        setAiMessage("AI connection verified successfully.");
      } else {
        setAiMessage(
          getFriendlyAiError(data.validation_error ?? data.error) || "Failed to verify AI connection."
        );
      }
      await refreshStatus();
    } catch {
      setAiMessage("Failed to verify AI connection.");
    } finally {
      setAiSaving(false);
    }
  };

  const handlePermissionToggle = async (permission: PermissionItem) => {
    try {
      await updatePermission(permission.id, !permission.granted);
      await refreshStatus();
    } catch {
      setAiMessage("Failed to update permission.");
    }
  };

  const handleTestNotification = async () => {
    setNotificationTesting(true);
    setMobileMessage("");
    try {
      await sendTestMobileNotification({
        title: "Sigorjob test",
        body: "If your phone is paired and open, you should see this within a few seconds.",
      });
      setMobileMessage("A test notification was queued. Keep the mobile app open and wait a few seconds.");
    } catch {
      setMobileMessage("Failed to queue a test notification.");
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
      setMobileMessage("Mobile connection was disconnected.");
      await refreshStatus();
    } catch {
      setMobileMessage("Failed to disconnect the mobile connection.");
    } finally {
      setDisconnecting(false);
    }
  };

  const aiSettingsCard = (
    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
      <div className="space-y-1">
        <h2 className="font-semibold text-gray-800">{t("ai_fallback_setup")}</h2>
        <p className="text-sm text-gray-600">
          {t("ai_fallback_desc")}
        </p>
      </div>
      <div className="rounded-lg border border-gray-100 bg-gray-50 p-4 space-y-3">
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
              {getFriendlyAiError(status.ai_validation_error) || "The key is saved, but the live AI connection is not verified yet."}
            </p>
            {status.ai_validation_error && (
              <div className="space-y-2">
                <button
                  type="button"
                  onClick={() => setShowAiErrorDetails((prev) => !prev)}
                  className="text-xs font-medium text-amber-800 underline underline-offset-2"
                >
                  {showAiErrorDetails
                    ? t("hide_ai_error_details", "상세 오류 숨기기")
                    : t("show_ai_error_details", "상세 오류 보기")}
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
            {t("ai_verified_desc", "실제 AI 연결 검증까지 완료되었습니다.")}
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
              {t("verify_connection", "연결 확인")}
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
      <div className="rounded-lg border border-gray-100 bg-white p-4 space-y-3">
        <div className="space-y-1">
          <p className="text-sm font-medium text-gray-900">{t("api_key_guide")}</p>
          <p className="text-xs text-gray-500 leading-5">
            {t("api_key_guide_desc")}
          </p>
        </div>
        <div className="space-y-3">
          <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-blue-900">Anthropic</p>
                <p className="text-xs text-blue-700">{t("currently_supported")}</p>
              </div>
              <a
                href="https://docs.anthropic.com/en/api/getting-started"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-blue-700 underline underline-offset-2"
              >
                {t("issuance_guide")}
              </a>
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
              <a
                href="https://platform.openai.com/docs/quickstart"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-gray-700 underline underline-offset-2"
              >
                {t("issuance_guide")}
              </a>
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
              <a
                href="https://ai.google.dev/tutorials/setup"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-gray-700 underline underline-offset-2"
              >
                {t("issuance_guide")}
              </a>
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
    <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
      <div className="space-y-1">
        <h2 className="font-semibold text-gray-800">{t("permissions_title")}</h2>
        <p className="text-sm text-gray-600">{t("permissions_desc")}</p>
      </div>
      {(status?.permissions ?? []).some((permission) => permission.risk === "high") && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 space-y-2">
          <p className="text-sm font-medium text-amber-900">민감한 작업 권한</p>
          <p className="text-xs text-amber-800 leading-5">
            결제, 구매 진행, 외부 서비스 조작처럼 실수 비용이 큰 기능은 여기서 별도로 관리하세요.
          </p>
          <div className="space-y-3">
            {(status?.permissions ?? [])
              .filter((permission) => permission.risk === "high")
              .map((permission) => (
                <div
                  key={permission.id}
                  className="rounded-lg border border-amber-200 bg-white p-4 flex items-start justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-gray-900">{permission.title}</p>
                      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800">
                        High risk
                      </span>
                    </div>
                    <p className="text-xs text-gray-600 leading-5">{permission.description}</p>
                    <p className="text-xs text-gray-500">Source: {permission.source}</p>
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
              ))}
          </div>
        </div>
      )}
      <div className="space-y-3">
        {(status?.permissions ?? [])
          .filter((permission) => permission.risk !== "high")
          .map((permission) => (
          <div
            key={permission.id}
            className="rounded-lg border border-gray-200 bg-gray-50 p-4 flex items-start justify-between gap-4"
          >
            <div className="space-y-1">
              <p className="text-sm font-medium text-gray-900">{permission.title}</p>
              <p className="text-xs text-gray-600 leading-5">{permission.description}</p>
              <p className="text-xs text-gray-500">Source: {permission.source}</p>
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
        ))}
      </div>
    </div>
  );

  return (
    <main className="min-h-screen bg-gray-50 px-4 py-10">
      <div className="mx-auto w-full max-w-5xl space-y-6">
        <div className="flex justify-end">
          <LanguageToggle />
        </div>
        {status?.cloudflared_installed === false && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 space-y-2">
            <h2 className="text-sm font-semibold text-amber-900">
              Remote access component is unavailable
            </h2>
            <p className="text-sm text-amber-800 leading-6">
              Mobile pairing and remote access will not work until `cloudflared` is
              available to this app.
            </p>
            <p className="text-xs text-amber-700 leading-5">
              Packaged desktop builds should include it automatically. If you are
              running from source, install `cloudflared` or set the
              `CLOUDFLARED_PATH` environment variable, then reopen this page.
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
            <div className="space-y-2">
              <h1 className="text-2xl font-bold text-gray-900">{t("setup_title")}</h1>
              <p className="max-w-2xl text-gray-500 text-sm">
                {t("setup_desc")}
              </p>
            </div>
            <section className="grid gap-6 xl:grid-cols-[1.08fr_0.92fr]">
              <div className="space-y-6">
                <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-4">
                  <div className="space-y-1">
                    <h2 className="font-semibold text-gray-800">{t("mobile_connection", "모바일 연결")}</h2>
                    <p className="text-sm text-gray-600">
                      {t("cloudflare_tunnel_desc")}
                    </p>
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
                  <p className="text-xs text-gray-500 leading-5">
                    {t("packaged_note")}
                  </p>
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
                      {selectedMode === "quick" ? t("start_quick_tunnel") : t("setup_named_tunnel")}
                    </button>
                    <a
                      href="https://one.dash.cloudflare.com/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="rounded-lg bg-orange-500 px-4 py-2 text-sm font-medium text-white hover:bg-orange-600"
                    >
                      {t("open_cloudflare_dashboard")}
                    </a>
                  </div>
                </div>

                {permissionsCard}
              </div>

              <div className="space-y-6">
                {aiSettingsCard}

                <div className="bg-white border border-gray-200 rounded-lg p-5 space-y-3">
                  <div className="space-y-1">
                    <h2 className="font-semibold text-gray-800">
                      {t("connection_guidance", "바로가기")}
                    </h2>
                    <p className="text-sm text-gray-600">
                      {t(
                        "connection_guidance_desc",
                        "지금은 연결을 시작하거나, 나중에 로컬 전용으로 먼저 써볼 수 있습니다."
                      )}
                    </p>
                  </div>
                  <button
                    onClick={() => router.push("/")}
                    className="w-full rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-50"
                  >
                    {t("use_local_only_later")}
                  </button>
                </div>
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
              <p className="text-sm text-gray-500">
                {t("tunnel_token_desc")}
              </p>
            </div>
            <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
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
                  배포된 데스크톱 앱이라면 번들 문제가 있을 수 있습니다. 소스 실행 환경이라면
                  `cloudflared` 설치가 필요합니다.
                </p>
              )}
              <p className="text-xs text-gray-500 leading-5">
                정식 Tunnel은 Cloudflare 쪽에서 public hostname 또는 route 설정까지
                되어 있어야 실제 외부 URL이 활성화됩니다.
              </p>
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
          <div className="text-center space-y-4">
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
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 space-y-2">
              <p className="text-xs text-green-600">
                {selectedMode === "quick" ? "Quick Tunnel" : "정식 Tunnel"}
              </p>
              <p className="text-sm text-green-700 font-medium">{t("tunnel_url")}</p>
              <p className="font-mono text-sm text-green-800 break-all">{tunnelUrl}</p>
              <p className="text-xs text-green-600">
                {t("open_remotely_desc")}
              </p>
            </div>
            <section className="grid gap-6 xl:grid-cols-[1.08fr_0.92fr]">
              <div className="space-y-6">
                <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-3">
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-gray-900">
                      {t("mobile_operations", "모바일 운영")}
                    </p>
                    <p className="text-xs text-gray-600 leading-5">
                      {t(
                        "mobile_operations_desc",
                        "테스트 알림을 보내거나 연결을 끊고 다시 페어링할 수 있습니다."
                      )}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={handleTestNotification}
                      disabled={notificationTesting}
                      className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 disabled:opacity-50"
                    >
                      {notificationTesting ? "Sending..." : "Send test notification"}
                    </button>
                    <button
                      onClick={handleDisconnectTunnel}
                      disabled={disconnecting}
                      className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-700 disabled:opacity-50"
                    >
                      {disconnecting ? "Disconnecting..." : "Disconnect mobile connection"}
                    </button>
                  </div>
                </div>
                {permissionsCard}
              </div>
              <div className="space-y-6">
                {aiSettingsCard}
              </div>
            </section>
            <button
              onClick={() => router.push("/")}
              className="w-full py-2 px-4 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium"
            >
              {t("start")}
            </button>
          </>
        )}

      </div>
    </main>
  );
}

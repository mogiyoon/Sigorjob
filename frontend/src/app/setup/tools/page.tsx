"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useLanguage } from "@/components/LanguageProvider";
import {
  getMcpPresets,
  getSetupStatus,
  installMcpPreset,
  installPlaywright,
  type McpPresetItem,
  type SetupStatusResponse,
  uninstallMcpPreset,
} from "@/lib/api";

function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export default function SetupToolsPage() {
  const { t } = useLanguage();
  const [status, setStatus] = useState<SetupStatusResponse | null>(null);
  const [mcpPresets, setMcpPresets] = useState<McpPresetItem[]>([]);
  const [pageMessage, setPageMessage] = useState("");
  const [pageError, setPageError] = useState("");
  const [installingPlaywrightNow, setInstallingPlaywrightNow] = useState(false);
  const [pendingPresetId, setPendingPresetId] = useState<string | null>(null);

  const refreshStatus = async () => {
    const nextStatus = await getSetupStatus();
    setStatus(nextStatus);
  };

  const refreshPresets = async () => {
    const presets = await getMcpPresets();
    setMcpPresets(presets);
  };

  useEffect(() => {
    void Promise.all([refreshStatus(), refreshPresets()]).catch(() => {
      setPageError(t("error_network", "Check your network connection and try again."));
    });

    const intervalId = window.setInterval(() => {
      void Promise.all([refreshStatus(), refreshPresets()]).catch(() => undefined);
    }, 3000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [t]);

  const handleInstallPlaywright = async () => {
    setInstallingPlaywrightNow(true);
    setPageError("");
    setPageMessage("");
    try {
      const result = await installPlaywright();
      if (!result.success) {
        setPageError(result.error || t("playwright_install_failed", "Could not install Playwright."));
        return;
      }
      setPageMessage(
        t("playwright_install_success", "Playwright installation finished.")
      );
      await refreshStatus();
    } catch {
      setPageError(t("playwright_install_failed", "Could not install Playwright."));
    } finally {
      setInstallingPlaywrightNow(false);
    }
  };

  const handlePresetAction = async (preset: McpPresetItem) => {
    setPendingPresetId(preset.id);
    setPageError("");
    setPageMessage("");
    try {
      const result = preset.installed
        ? await uninstallMcpPreset(preset.id)
        : await installMcpPreset(preset.id);
      if (!result.success) {
        setPageError(
          result.error ||
            (preset.installed
              ? t("mcp_preset_uninstall_failed", "Could not uninstall the MCP preset.")
              : t("mcp_preset_install_failed", "Could not install the MCP preset."))
        );
        return;
      }
      await Promise.all([refreshStatus(), refreshPresets()]);
    } catch {
      setPageError(
        preset.installed
          ? t("mcp_preset_uninstall_failed", "Could not uninstall the MCP preset.")
          : t("mcp_preset_install_failed", "Could not install the MCP preset.")
      );
    } finally {
      setPendingPresetId(null);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 px-4 py-10">
      <div className="mx-auto w-full max-w-5xl space-y-6">
        <Link
          href="/setup"
          className="inline-flex rounded-full border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50"
        >
          {t("setup_back_to_settings", "← 설정으로 돌아가기")}
        </Link>
        <section className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="space-y-1">
            <h1 className="text-2xl font-semibold tracking-tight text-gray-950">
              {t("setup_tools_title", "도구 설정")}
            </h1>
            <p className="text-sm text-gray-500">
              {t(
                "tools_desc",
                "Install local tools required for browser automation and similar tasks."
              )}
            </p>
          </div>
        </section>

        {pageMessage && (
          <div className="rounded-2xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-800">
            {pageMessage}
          </div>
        )}
        {pageError && (
          <div className="rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
            {pageError}
          </div>
        )}

        <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-semibold text-gray-950">{t("playwright", "Playwright")}</h2>
                <span
                  className={cn(
                    "rounded-full px-2.5 py-1 text-xs font-medium",
                    status?.playwright.installed && status.playwright.browsers_installed
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-gray-100 text-gray-600"
                  )}
                >
                  {status?.playwright.installed
                    ? t("installed_short", "Installed")
                    : t("not_installed_short", "Not installed")}
                </span>
              </div>
              <p className="text-sm leading-6 text-gray-600">
                {t(
                  "playwright_desc",
                  "Required for browser automation tasks that open and control Chromium."
                )}
              </p>
              <p className="text-xs text-gray-500">
                {t(
                  "playwright_install_notice",
                  "Installing Playwright may take a few minutes because Chromium also needs to be downloaded."
                )}
              </p>
              <p className="text-xs text-gray-500">
                {status?.playwright.browsers_installed
                  ? t("connected_short", "Connected")
                  : t("needs_check_short", "Check")}
              </p>
            </div>
            <button
              type="button"
              onClick={() => void handleInstallPlaywright()}
              disabled={installingPlaywrightNow || Boolean(status?.playwright.installed)}
              className="rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {installingPlaywrightNow ? t("installing_short", "Installing...") : t("install", "Install")}
            </button>
          </div>
        </section>

        <section className="space-y-4">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-gray-950">
              {t("mcp_presets_title", "MCP Presets")}
            </h2>
            <p className="text-sm text-gray-600">
              {t(
                "mcp_presets_desc",
                "Install or remove ready-made MCP bundles with one click."
              )}
            </p>
          </div>

          {mcpPresets.length === 0 && (
            <div className="rounded-2xl border border-dashed border-gray-300 bg-white px-4 py-5 text-sm text-gray-500">
              {t("mcp_presets_empty", "No MCP presets are available right now.")}
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            {mcpPresets.map((preset) => (
              <article
                key={preset.id}
                className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm"
              >
                <div className="flex h-full flex-col justify-between gap-4">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-base font-semibold text-gray-950">{preset.name}</h3>
                      <span
                        className={cn(
                          "rounded-full px-2.5 py-1 text-xs font-medium",
                          preset.installed
                            ? "bg-emerald-100 text-emerald-700"
                            : "bg-gray-100 text-gray-600"
                        )}
                      >
                        {preset.installed
                          ? t("installed_short", "Installed")
                          : t("not_installed_short", "Not installed")}
                      </span>
                    </div>
                    <p className="text-sm leading-6 text-gray-600">{preset.description}</p>
                  </div>
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={() => void handlePresetAction(preset)}
                      disabled={pendingPresetId === preset.id}
                      className={cn(
                        "rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50",
                        preset.installed
                          ? "border border-red-200 text-red-700"
                          : "bg-gray-900 text-white"
                      )}
                    >
                      {pendingPresetId === preset.id
                        ? preset.installed
                          ? t("uninstalling_short", "Uninstalling...")
                          : t("installing_short", "Installing...")
                        : preset.installed
                          ? t("uninstall", "Uninstall")
                          : t("install", "Install")}
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}

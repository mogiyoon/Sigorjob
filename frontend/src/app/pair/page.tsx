"use client";

import { useEffect, useState } from "react";
import QRCode from "qrcode";
import LanguageToggle from "@/components/LanguageToggle";
import { useLanguage } from "@/components/LanguageProvider";
import { localApiFetch } from "@/lib/api";

interface PairData {
  status: "ready" | "tunnel_not_ready" | "dependency_missing";
  tunnel_mode?: "none" | "quick" | "cloudflare";
  url: string | null;
  qr_data: string | null;
  token: string | null;
  raw?: string | null;
  error?: string | null;
}

export default function PairPage() {
  const { t } = useLanguage();
  const [data, setData] = useState<PairData | null>(null);
  const [copied, setCopied] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [qrImage, setQrImage] = useState<string | null>(null);

  const fetchPairData = async () => {
    try {
      setLoadError(null);
      const res = await localApiFetch("/pair/data");
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const json = (await res.json()) as PairData;
      setData(json);
    } catch {
      setLoadError(t("pair_load_error", "Could not load phone connection details. Please try again in a moment."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPairData();
    const interval = setInterval(fetchPairData, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const renderQr = async () => {
      if (!data?.qr_data) {
        setQrImage(null);
        return;
      }
      try {
        const image = await QRCode.toDataURL(data.qr_data, {
          width: 240,
          margin: 2,
          color: {
            dark: "#111827",
            light: "#ffffff",
          },
        });
        setQrImage(image);
      } catch {
        setQrImage(null);
      }
    };

    renderQr();
  }, [data?.qr_data]);

  const copyToken = () => {
    if (!data?.token) return;
    navigator.clipboard.writeText(data.token);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const copyUrl = () => {
    if (!data?.url) return;
    navigator.clipboard.writeText(data.url);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2000);
  };

  if (loading && !data) {
    return (
      <main className="min-h-screen bg-gray-50 flex flex-col items-center py-12 px-4">
        <div className="w-full max-w-md rounded-xl border border-gray-200 bg-white p-6 text-center text-gray-500">
          {t("loading_mobile_pair")}
        </div>
      </main>
    );
  }

  const modeLabel =
    data?.tunnel_mode === "quick"
      ? "Quick Tunnel"
      : data?.tunnel_mode === "cloudflare"
        ? t("named_tunnel")
        : t("not_set");

  return (
    <main className="min-h-screen bg-gray-50 flex flex-col items-center py-12 px-4">
      <div className="w-full max-w-md space-y-6">
        <div className="flex justify-end">
          <LanguageToggle />
        </div>
        <h1 className="text-2xl font-bold text-gray-900">{t("mobile_app_connect")}</h1>
        <p className="text-sm text-gray-500 leading-6">
          {t("mobile_app_connect_desc")}
        </p>

        {loadError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 space-y-2">
            <p className="text-sm font-medium text-red-800">{loadError}</p>
            <button
              onClick={fetchPairData}
              className="text-sm text-red-700 underline underline-offset-2"
            >
              {t("retry_loading_pair")}
            </button>
          </div>
        )}

        {data && data.status === "dependency_missing" ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 space-y-2">
            <p className="text-red-700 text-sm font-medium">
              {t("remote_component_unavailable")}
            </p>
            <p className="text-red-600 text-sm leading-6">
              {t(
                "pair_dependency_missing_desc",
                "Packaged desktop builds usually include the connection tool automatically. If you are running from source, install cloudflared or set CLOUDFLARED_PATH and try again."
              )}
            </p>
            {data.error && (
              <p className="text-red-500 text-xs">{data.error}</p>
            )}
          </div>
        ) : data && data.status === "tunnel_not_ready" ? (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <p className="text-yellow-700 text-sm">
              {t("tunnel_starting")}
            </p>
            <p className="text-yellow-700 text-xs mt-1">
              {t("current_mode")}: {modeLabel}
            </p>
            {data.error && <p className="text-yellow-500 text-xs mt-1">{data.error}</p>}
            <a
              href="/setup"
              className="inline-block mt-3 text-sm text-yellow-800 underline underline-offset-2"
            >
              {t("go_to_setup")}
            </a>
          </div>
        ) : data ? (
          <div className="space-y-4">
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 space-y-2">
              <p className="text-xs text-green-700">{modeLabel}</p>
              <p className="text-sm font-medium text-green-900">{t("pairing_ready")}</p>
              <p className="text-sm text-green-800 leading-6">
                {t("pairing_ready_desc")}
              </p>
            </div>

            <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3 shadow-sm">
              {qrImage && (
                <div className="flex flex-col items-center gap-3 rounded-lg border border-gray-100 bg-gray-50 p-4">
                  <img
                    src={qrImage}
                    alt="Mobile pairing QR code"
                    className="h-60 w-60 rounded-lg border border-gray-200 bg-white p-2"
                  />
                  <p className="text-xs text-gray-500 text-center leading-5">
                    {t("qr_ready_desc")}
                  </p>
                </div>
              )}
              <p className="text-xs text-gray-500">{modeLabel}</p>
              <p className="text-sm text-gray-600">{t("tunnel_url")}</p>
              <div className="space-y-2">
                <p className="font-mono text-sm text-blue-600 break-all">{data.url}</p>
                <button
                  onClick={copyUrl}
                  className="px-3 py-1 text-sm bg-gray-200 hover:bg-gray-300 rounded"
                >
                  {copiedUrl ? t("url_copied") : t("copy_url")}
                </button>
              </div>
              {data.tunnel_mode === "quick" && (
                <p className="text-xs text-amber-700 leading-5">
                  {t("quick_url_note")}
                </p>
              )}
            </div>

            <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3 shadow-sm">
              <p className="text-sm text-gray-600">{t("connection_method")}</p>
              <p className="text-sm text-gray-500 leading-6">
                {t("connection_method_desc")}
              </p>
            </div>

            <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-2 shadow-sm">
              <p className="text-sm text-gray-600">{t("auth_token_manual")}</p>
              <div className="flex gap-2">
                <code className="flex-1 text-xs bg-gray-50 p-2 rounded border overflow-auto">
                  {data.token}
                </code>
                <button
                  onClick={copyToken}
                  className="px-3 py-1 text-sm bg-gray-200 hover:bg-gray-300 rounded"
                >
                  {copied ? t("copied") : t("copy")}
                </button>
              </div>
            </div>

            <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-2">
              <p className="text-sm text-gray-600">{t("mobile_steps")}</p>
              <ol className="list-decimal pl-5 text-sm text-gray-500 space-y-1">
                <li>{t("mobile_step_1")}</li>
                <li>{t("mobile_step_2")}</li>
                <li>{t("mobile_step_3")}</li>
              </ol>
            </div>
          </div>
        ) : null}

        <a href="/" className="block text-center text-sm text-gray-500 hover:text-gray-700">
          {t("back_to_main")}
        </a>
      </div>
    </main>
  );
}

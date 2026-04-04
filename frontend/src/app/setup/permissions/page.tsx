"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useLanguage } from "@/components/LanguageProvider";
import { getSetupStatus, type PermissionItem, type SetupStatusResponse, updatePermission } from "@/lib/api";

type PermissionGroupKey = "core" | "service" | "sensitive" | "advanced";

function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function getPermissionGroup(permission: PermissionItem): PermissionGroupKey {
  if (permission.advanced) return "advanced";
  if (permission.group === "core_access") return "core";
  if (permission.group === "service_extensions") return "service";
  if (permission.group === "sensitive_actions" || permission.risk === "high") return "sensitive";
  return "advanced";
}

function PermissionGroupSection({
  description,
  items,
  onToggle,
  pendingPermissionId,
  title,
}: {
  description: string;
  items: PermissionItem[];
  onToggle: (permission: PermissionItem) => void;
  pendingPermissionId: string | null;
  title: string;
}) {
  const { t } = useLanguage();

  return (
    <section className="space-y-4 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="space-y-1">
        <h2 className="text-lg font-semibold text-gray-950">{title}</h2>
        <p className="text-sm text-gray-600">{description}</p>
      </div>
      <div className="space-y-3">
        {items.map((permission) => {
          const busy = pendingPermissionId === permission.id;
          return (
            <article
              key={permission.id}
              className="flex flex-wrap items-start justify-between gap-4 rounded-2xl border border-gray-100 bg-gray-50 p-4"
            >
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold text-gray-900">{permission.title}</h3>
                  <span
                    className={cn(
                      "rounded-full px-2.5 py-1 text-xs font-medium",
                      permission.granted
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-gray-100 text-gray-600"
                    )}
                  >
                    {permission.granted
                      ? t("permission_allowed", "Allowed")
                      : t("permission_not_allowed", "Not allowed")}
                  </span>
                </div>
                <p className="max-w-2xl text-sm leading-6 text-gray-600">{permission.description}</p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={permission.granted}
                onClick={() => onToggle(permission)}
                disabled={busy}
                className={cn(
                  "inline-flex min-w-28 justify-center rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50",
                  permission.granted
                    ? "bg-gray-900 text-white"
                    : "border border-gray-300 bg-white text-gray-700"
                )}
              >
                {busy
                  ? t("saving", "Saving...")
                  : permission.granted
                    ? t("permission_allowed", "Allowed")
                    : t("permission_not_allowed", "Not allowed")}
              </button>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export default function SetupPermissionsPage() {
  const { t } = useLanguage();
  const [status, setStatus] = useState<SetupStatusResponse | null>(null);
  const [pendingPermissionId, setPendingPermissionId] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [pageError, setPageError] = useState("");

  const refreshStatus = async () => {
    const nextStatus = await getSetupStatus();
    setStatus(nextStatus);
  };

  useEffect(() => {
    void refreshStatus().catch(() => {
      setPageError(t("error_network", "Check your network connection and try again."));
    });

    const intervalId = window.setInterval(() => {
      void refreshStatus().catch(() => undefined);
    }, 3000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [t]);

  const groupedPermissions = useMemo(() => {
    const groups: Record<PermissionGroupKey, PermissionItem[]> = {
      core: [],
      service: [],
      sensitive: [],
      advanced: [],
    };

    for (const permission of status?.permissions ?? []) {
      groups[getPermissionGroup(permission)].push(permission);
    }

    return groups;
  }, [status]);

  const handleToggle = async (permission: PermissionItem) => {
    setPendingPermissionId(permission.id);
    setPageError("");
    setStatus((current) =>
      current
        ? {
            ...current,
            permissions: current.permissions.map((item) =>
              item.id === permission.id ? { ...item, granted: !item.granted } : item
            ),
          }
        : current
    );

    try {
      await updatePermission(permission.id, !permission.granted);
      await refreshStatus();
    } catch {
      setPageError(t("permission_update_failed", "Could not update the permission."));
      setStatus((current) =>
        current
          ? {
              ...current,
              permissions: current.permissions.map((item) =>
                item.id === permission.id ? { ...item, granted: permission.granted } : item
              ),
            }
          : current
      );
    } finally {
      setPendingPermissionId(null);
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
              {t("setup_permissions_title", "권한 관리")}
            </h1>
            <p className="text-sm text-gray-500">
              {t(
                "permissions_desc",
                "Review which features need permission and turn them on or off when needed."
              )}
            </p>
          </div>
        </section>

        {pageError && (
          <div className="rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
            {pageError}
          </div>
        )}

        <PermissionGroupSection
          title={t("core_permissions_title", "Core access")}
          description={t(
            "core_permissions_desc",
            "Manage the first-run experiences people notice most, like mobile access and AI help."
          )}
          items={groupedPermissions.core}
          onToggle={handleToggle}
          pendingPermissionId={pendingPermissionId}
        />

        <PermissionGroupSection
          title={t("service_permissions_title", "Service extensions")}
          description={t(
            "service_permissions_desc",
            "Use these when Gmail, Calendar, or future MCP-style add-ons should be available."
          )}
          items={groupedPermissions.service}
          onToggle={handleToggle}
          pendingPermissionId={pendingPermissionId}
        />

        <PermissionGroupSection
          title={t("sensitive_permissions_title", "Sensitive permissions")}
          description={t(
            "sensitive_permissions_desc",
            "Manage payment, purchase, and external service actions separately here."
          )}
          items={groupedPermissions.sensitive}
          onToggle={handleToggle}
          pendingPermissionId={pendingPermissionId}
        />

        <section className="space-y-4 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-1">
              <h2 className="text-lg font-semibold text-gray-950">
                {t("advanced_permissions_title", "Advanced permissions")}
              </h2>
              <p className="text-sm text-gray-600">
                {t(
                  "advanced_permissions_desc",
                  "Keep rarely used or developer-oriented permissions tucked away here."
                )}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowAdvanced((current) => !current)}
              className="text-sm font-medium text-gray-700 underline underline-offset-2"
            >
              {showAdvanced
                ? t("hide_advanced_permissions", "Hide advanced")
                : t("show_advanced_permissions", "Show advanced")}
            </button>
          </div>
          {showAdvanced && (
            <div className="space-y-3">
              {groupedPermissions.advanced.map((permission) => {
                const busy = pendingPermissionId === permission.id;
                return (
                  <article
                    key={permission.id}
                    className="flex flex-wrap items-start justify-between gap-4 rounded-2xl border border-gray-100 bg-gray-50 p-4"
                  >
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-sm font-semibold text-gray-900">{permission.title}</h3>
                        <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600">
                          {permission.granted
                            ? t("permission_allowed", "Allowed")
                            : t("permission_not_allowed", "Not allowed")}
                        </span>
                      </div>
                      <p className="max-w-2xl text-sm leading-6 text-gray-600">
                        {permission.description}
                      </p>
                    </div>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={permission.granted}
                      onClick={() => handleToggle(permission)}
                      disabled={busy}
                      className={cn(
                        "inline-flex min-w-28 justify-center rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50",
                        permission.granted
                          ? "bg-gray-900 text-white"
                          : "border border-gray-300 bg-white text-gray-700"
                      )}
                    >
                      {busy
                        ? t("saving", "Saving...")
                        : permission.granted
                          ? t("permission_allowed", "Allowed")
                          : t("permission_not_allowed", "Not allowed")}
                    </button>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

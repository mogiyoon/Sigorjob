"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useLanguage } from "@/components/LanguageProvider";
import { openExternalUrl } from "@/lib/external";
import {
  authorizeConnection,
  callbackConnection,
  deleteCustomConnection,
  disconnectConnection,
  getSetupStatus,
  type ConnectionItem,
  type SetupStatusResponse,
  upsertCustomConnection,
} from "@/lib/api";

type BuiltinConnectionDefinition = {
  id: "gmail" | "google_calendar";
  titleKey: string;
  titleFallback: string;
  descriptionKey: string;
  descriptionFallback: string;
  hintKey: string;
  hintFallback: string;
};

const BUILTIN_CONNECTIONS: BuiltinConnectionDefinition[] = [
  {
    id: "gmail",
    titleKey: "gmail_connection_title",
    titleFallback: "Gmail",
    descriptionKey: "gmail_connection_desc",
    descriptionFallback: "Used for drafting emails and sending real Gmail messages.",
    hintKey: "gmail_connect_hint",
    hintFallback: "Connect Gmail before asking Sigorjob to send real email.",
  },
  {
    id: "google_calendar",
    titleKey: "google_calendar_connection_title",
    titleFallback: "Google Calendar",
    descriptionKey: "google_calendar_connection_desc",
    descriptionFallback: "Used for creating events and checking calendar schedules.",
    hintKey: "calendar_connect_hint",
    hintFallback: "Connect Calendar before asking Sigorjob to create real events.",
  },
];

const CUSTOM_CAPABILITY = "create_calendar_event";
const CUSTOM_PERMISSION = "calendar_event_creation";

function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function createFallbackConnection(definition: BuiltinConnectionDefinition): ConnectionItem {
  return {
    id: definition.id,
    title: definition.titleFallback,
    description: definition.descriptionFallback,
    provider: "google",
    kind: "external",
    connection_type: "oauth_or_mcp",
    auth_type: "oauth_or_mcp",
    driver_id: definition.id,
    capabilities: [],
    capability_permissions: {},
    required_permissions: ["external_connection_access"],
    configured: false,
    verified: false,
    available: false,
    account_label: null,
    metadata: {},
    status: "not_connected",
    next_action: "connect",
  };
}

function getConnectionStatusLabel(
  connection: ConnectionItem,
  t: (key: string, fallback?: string) => string
) {
  if (connection.verified || connection.status === "connected") {
    return t("connected_short", "Connected");
  }
  if (connection.configured || connection.status === "configured") {
    return t("needs_check_short", "Check");
  }
  if (connection.status === "planned") {
    return t("planned_short", "Planned");
  }
  return t("not_set", "Not set");
}

function getConnectionHint(
  connection: ConnectionItem,
  t: (key: string, fallback?: string) => string,
  definition: BuiltinConnectionDefinition
) {
  if (connection.verified || connection.status === "connected") {
    return t("connection_manage_hint", "Ready to use in tasks.");
  }
  if (connection.configured || connection.status === "configured") {
    return t("connection_verify_hint", "Connected info exists, but it still needs to be checked.");
  }
  return t(definition.hintKey, definition.hintFallback);
}

function getCustomConnectionHint(
  connection: ConnectionItem,
  t: (key: string, fallback?: string) => string
) {
  if (connection.verified || connection.status === "connected") {
    return t("connection_manage_hint", "Ready to use in tasks.");
  }
  if (connection.configured || connection.status === "configured") {
    return t("connection_verify_hint", "Connected info exists, but it still needs to be checked.");
  }
  return t("connection_connect_hint", "Connect this before using related actions.");
}

function ConnectionCard({
  actionLabel,
  busy,
  connection,
  description,
  hint,
  onAction,
  title,
}: {
  actionLabel: string;
  busy: boolean;
  connection: ConnectionItem;
  description: string;
  hint: string;
  onAction: () => void;
  title: string;
}) {
  const { t } = useLanguage();
  const connected = connection.verified || connection.status === "connected";

  return (
    <article className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold text-gray-950">{title}</h2>
            <span
              className={cn(
                "rounded-full px-2.5 py-1 text-xs font-medium",
                connected
                  ? "bg-emerald-100 text-emerald-700"
                  : connection.configured
                    ? "bg-amber-100 text-amber-700"
                    : "bg-gray-100 text-gray-600"
              )}
            >
              {getConnectionStatusLabel(connection, t)}
            </span>
          </div>
          <p className="max-w-2xl text-sm leading-6 text-gray-600">{description}</p>
          <p className="text-xs text-gray-500">
            {t("connection_status_label", "Status")}: {hint}
          </p>
          {connection.account_label && (
            <p className="text-xs font-medium text-gray-600">{connection.account_label}</p>
          )}
        </div>
        <button
          type="button"
          onClick={onAction}
          disabled={busy}
          className={cn(
            "rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50",
            connected
              ? "border border-red-200 text-red-700"
              : "bg-gray-900 text-white"
          )}
        >
          {busy ? t("connecting_oauth", "Connecting...") : actionLabel}
        </button>
      </div>
      {connection.required_permissions.length > 0 && (
        <p className="mt-4 text-xs leading-5 text-gray-500">
          {t(
            "connection_permissions_separate_hint",
            "If you want to allow real actions with this service, also turn on the related permission below."
          )}
        </p>
      )}
    </article>
  );
}

export default function SetupConnectionsPage() {
  const { t } = useLanguage();
  const [status, setStatus] = useState<SetupStatusResponse | null>(null);
  const [pageMessage, setPageMessage] = useState("");
  const [pageError, setPageError] = useState("");
  const [pendingConnectionId, setPendingConnectionId] = useState<string | null>(null);
  const [savingCustom, setSavingCustom] = useState(false);
  const [deletingCustomId, setDeletingCustomId] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [form, setForm] = useState({
    connectionId: "",
    title: "",
    provider: "",
    urlTemplate: "",
    titleTemplate: "",
  });

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

  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const state = params.get("state");
    const connectionId = params.get("connection_id");
    if (!code || !state || !connectionId) return;

    setPendingConnectionId(connectionId);
    setPageError("");
    void callbackConnection(connectionId, { code, state })
      .then((result) => {
        if (!result.success) {
          setPageError(
            result.error ||
              t("connection_callback_failed", "Could not finish the connection. Try again.")
          );
          return;
        }
        setPageMessage(t("connection_manage_hint", "Ready to use in tasks."));
        params.delete("code");
        params.delete("state");
        params.delete("connection_id");
        const nextQuery = params.toString();
        window.history.replaceState(
          {},
          "",
          `${window.location.pathname}${nextQuery ? `?${nextQuery}` : ""}`
        );
        return refreshStatus();
      })
      .catch(() => {
        setPageError(t("connection_callback_failed", "Could not finish the connection. Try again."));
      })
      .finally(() => {
        setPendingConnectionId(null);
      });
  }, [t]);

  const builtinConnections = useMemo(() => {
    const current = new Map((status?.connections ?? []).map((connection) => [connection.id, connection]));
    return BUILTIN_CONNECTIONS.map((definition) => ({
      definition,
      connection: current.get(definition.id) ?? createFallbackConnection(definition),
    }));
  }, [status]);

  const customConnections = useMemo(
    () =>
      (status?.connections ?? []).filter(
        (connection) =>
          connection.connection_type === "custom" || connection.driver_id === "template_connector"
      ),
    [status]
  );

  const handleAuthorize = async (connectionId: string) => {
    setPendingConnectionId(connectionId);
    setPageError("");
    setPageMessage("");
    try {
      const payload = await authorizeConnection(connectionId);
      setPageMessage(
        t(
          "connection_pending_message",
          "Waiting for the connection to finish. Complete the sign-in window, then the status will refresh here."
        )
      );
      await openExternalUrl(payload.auth_url);
    } catch {
      setPageError(t("connection_authorize_failed", "Could not start the connection flow."));
    } finally {
      setPendingConnectionId(null);
    }
  };

  const handleDisconnect = async (connectionId: string) => {
    setPendingConnectionId(connectionId);
    setPageError("");
    setPageMessage("");
    try {
      const result = await disconnectConnection(connectionId);
      if (!result.success) {
        setPageError(
          result.error || t("connection_disconnect_failed", "Could not disconnect the service.")
        );
        return;
      }
      await refreshStatus();
    } catch {
      setPageError(t("connection_disconnect_failed", "Could not disconnect the service."));
    } finally {
      setPendingConnectionId(null);
    }
  };

  const handleSaveCustom = async () => {
    if (!form.connectionId.trim() || !form.title.trim() || !form.urlTemplate.trim()) {
      setPageError(
        t("custom_connector_required_fields", "Enter a name and URL template first.")
      );
      return;
    }

    setSavingCustom(true);
    setPageError("");
    setPageMessage("");
    try {
      const result = await upsertCustomConnection({
        connection_id: form.connectionId.trim(),
        title: form.title.trim(),
        description: t(
          "custom_connector_default_description",
          "User-defined connector added from the settings screen."
        ),
        provider: form.provider.trim() || "custom",
        auth_type: "manual",
        driver_id: "template_connector",
        capabilities: [CUSTOM_CAPABILITY],
        capability_permissions: { [CUSTOM_CAPABILITY]: [CUSTOM_PERMISSION] },
        available: true,
        configured: false,
        verified: false,
        metadata: {
          url_template: form.urlTemplate.trim(),
          title_template: form.titleTemplate.trim(),
        },
      });
      if (!result.success) {
        setPageError(
          result.error || t("custom_connector_save_failed", "Could not save the custom connector.")
        );
        return;
      }
      setPageMessage(t("custom_connector_saved", "Custom connector saved."));
      setForm({
        connectionId: "",
        title: "",
        provider: "",
        urlTemplate: "",
        titleTemplate: "",
      });
      await refreshStatus();
    } catch {
      setPageError(t("custom_connector_save_failed", "Could not save the custom connector."));
    } finally {
      setSavingCustom(false);
    }
  };

  const handleDeleteCustom = async (connectionId: string) => {
    setDeletingCustomId(connectionId);
    setPageError("");
    setPageMessage("");
    try {
      const result = await deleteCustomConnection(connectionId);
      if (!result.success) {
        setPageError(
          result.error ||
            t("custom_connector_delete_failed", "Could not remove the custom connector.")
        );
        return;
      }
      setPageMessage(t("custom_connector_deleted", "Custom connector removed."));
      await refreshStatus();
    } catch {
      setPageError(t("custom_connector_delete_failed", "Could not remove the custom connector."));
    } finally {
      setDeletingCustomId(null);
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
              {t("setup_connections_title", "외부 서비스 연결")}
            </h1>
            <p className="text-sm text-gray-500">
              {t(
                "external_connections_desc",
                "Use one shared place for Gmail, Calendar, and future MCP tools."
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

        <section className="space-y-4">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-gray-950">
              {t("connected_services_title", "Connected or ready")}
            </h2>
            <p className="text-sm text-gray-600">
              {t(
                "external_connections_separate_hint",
                "This area only shows whether a service is connected. The actual allow/deny switches live in the permission section below."
              )}
            </p>
          </div>
          {builtinConnections.map(({ definition, connection }) => {
            const connected = connection.verified || connection.status === "connected";
            return (
              <ConnectionCard
                key={definition.id}
                actionLabel={
                  connected
                    ? t("disconnect_service", "Disconnect")
                    : t("connect_service", "Connect")
                }
                busy={pendingConnectionId === definition.id}
                connection={connection}
                description={t(definition.descriptionKey, definition.descriptionFallback)}
                hint={getConnectionHint(connection, t, definition)}
                onAction={() =>
                  void (connected
                    ? handleDisconnect(definition.id)
                    : handleAuthorize(definition.id))
                }
                title={t(definition.titleKey, definition.titleFallback)}
              />
            );
          })}
        </section>

        <section className="space-y-4">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold text-gray-950">
              {t("custom_connectors_title", "Custom connectors")}
            </h2>
            <p className="text-sm text-gray-600">
              {t(
                "custom_connectors_desc",
                "Add shared connectors with capabilities and URL templates instead of building one-off service flows."
              )}
            </p>
          </div>

          {customConnections.map((connection) => (
            <article
              key={connection.id}
              className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm"
            >
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-base font-semibold text-gray-950">{connection.title}</h3>
                    <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-600">
                      {getConnectionStatusLabel(connection, t)}
                    </span>
                  </div>
                  <p className="text-sm leading-6 text-gray-600">{connection.description}</p>
                  <p className="text-xs text-gray-500">{getCustomConnectionHint(connection, t)}</p>
                </div>
                <button
                  type="button"
                  onClick={() => void handleDeleteCustom(connection.id)}
                  disabled={deletingCustomId === connection.id}
                  className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-700 disabled:opacity-50"
                >
                  {deletingCustomId === connection.id ? t("saving", "Saving...") : t("remove")}
                </button>
              </div>
            </article>
          ))}

          <article className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
            <div className="space-y-4">
              <div className="space-y-1">
                <p className="text-sm font-medium text-gray-900">
                  {t("custom_connectors_title", "Custom connectors")}
                </p>
                <p className="text-xs leading-5 text-gray-500">
                  {t(
                    "custom_connector_hint",
                    "The first UI only supports the create_calendar_event capability. Use placeholders like {title}, {details}, and {dates}."
                  )}
                </p>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <input
                  value={form.connectionId}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, connectionId: event.target.value }))
                  }
                  placeholder={t("custom_connector_id_placeholder", "Example: shared_calendar")}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
                <input
                  value={form.title}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, title: event.target.value }))
                  }
                  placeholder={t("custom_connector_title_placeholder", "Example: Shared calendar")}
                  className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                />
              </div>
              <textarea
                value={form.urlTemplate}
                onChange={(event) =>
                  setForm((current) => ({ ...current, urlTemplate: event.target.value }))
                }
                placeholder={t(
                  "custom_connector_url_placeholder",
                  "URL template, e.g. https://calendar.example.com/new?title={title}&dates={dates}"
                )}
                rows={3}
                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
              />
              <div className="space-y-3">
                <button
                  type="button"
                  onClick={() => setShowAdvanced((current) => !current)}
                  className="text-sm font-medium text-gray-700 underline underline-offset-2"
                >
                  {showAdvanced
                    ? t("hide_connector_advanced", "Hide advanced fields")
                    : t("show_connector_advanced", "Show advanced fields")}
                </button>
                {showAdvanced && (
                  <div className="grid gap-3 md:grid-cols-2">
                    <input
                      value={form.provider}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, provider: event.target.value }))
                      }
                      placeholder={t(
                        "custom_connector_provider_placeholder",
                        "Example: custom / mcp / internal"
                      )}
                      className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                    />
                    <input
                      value={form.titleTemplate}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, titleTemplate: event.target.value }))
                      }
                      placeholder={t(
                        "custom_connector_title_template_placeholder",
                        "Title template, e.g. {title} schedule"
                      )}
                      className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
                    />
                  </div>
                )}
              </div>
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => void handleSaveCustom()}
                  disabled={savingCustom}
                  className="rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                >
                  {savingCustom ? t("saving", "Saving...") : t("save_custom_connector", "Save connector")}
                </button>
              </div>
            </div>
          </article>
        </section>
      </div>
    </main>
  );
}

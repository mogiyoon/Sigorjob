"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import ApprovalPanel from "@/components/ApprovalPanel";
import CommandInput from "@/components/CommandInput";
import ConfirmDialog from "@/components/ConfirmDialog";
import LanguageToggle from "@/components/LanguageToggle";
import { useLanguage } from "@/components/LanguageProvider";
import SchedulePanel from "@/components/SchedulePanel";
import TaskCard from "@/components/TaskCard";
import {
  ApprovalItem,
  continueTaskWithAi,
  deleteTask,
  deleteTasks,
  getBaseUrl,
  listApprovals,
  listSchedules,
  listTasks,
  pollUntilDone,
  retryTask,
  ScheduleItem,
  sendCommand,
  TaskResponse,
  UnauthorizedError,
} from "@/lib/api";

type DashboardTab = "execute" | "routines" | "recent";
type ConfirmAction =
  | { kind: "delete-one"; taskId: string }
  | { kind: "delete-many"; taskIds: string[] }
  | null;

function CircleIconButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      aria-label={label}
      title={label}
      onClick={onClick}
      className="flex h-10 w-10 items-center justify-center rounded-full border border-gray-200 bg-white text-gray-700 shadow-sm hover:bg-gray-50"
    >
      {children}
    </button>
  );
}

export default function Home() {
  const router = useRouter();
  const { t } = useLanguage();
  const [activeTab, setActiveTab] = useState<DashboardTab>("execute");
  const [infoModal, setInfoModal] = useState<"mobile" | "ai" | null>(null);
  const [tasks, setTasks] = useState<TaskResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [tunnelActive, setTunnelActive] = useState<boolean | null>(null);
  const [cloudflaredInstalled, setCloudflaredInstalled] = useState<boolean | null>(null);
  const [isLocalUi, setIsLocalUi] = useState(false);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [schedules, setSchedules] = useState<ScheduleItem[]>([]);
  const [deletingTaskId, setDeletingTaskId] = useState<string | null>(null);
  const [retryingTaskId, setRetryingTaskId] = useState<string | null>(null);
  const [continuingAiTaskId, setContinuingAiTaskId] = useState<string | null>(null);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [authExpired, setAuthExpired] = useState(false);
  const [selectedCompletedTaskIds, setSelectedCompletedTaskIds] = useState<string[]>([]);
  const [completedFilter, setCompletedFilter] = useState<"all" | "done" | "failed" | "cancelled">("all");
  const [aiConfigured, setAiConfigured] = useState<boolean | null>(null);
  const [aiVerified, setAiVerified] = useState<boolean | null>(null);
  const [aiValidationError, setAiValidationError] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null);
  const refreshInFlight = useRef(false);

  useEffect(() => {
    const localUi =
      typeof window !== "undefined" &&
      ["127.0.0.1", "localhost", "tauri.localhost"].includes(window.location.hostname);
    setIsLocalUi(localUi);

    if (!localUi) {
      refreshDashboard();
      return;
    }

    fetch(`${getBaseUrl()}/setup/status`)
      .then((r) => r.json())
      .then((data) => {
        setTunnelActive(data.tunnel_active);
        setCloudflaredInstalled(data.cloudflared_installed);
        setAiConfigured(Boolean(data.ai_configured));
        setAiVerified(Boolean(data.ai_verified));
        setAiValidationError(data.ai_validation_error ?? null);
      })
      .catch(() => {
        // ignore local bootstrap failures
      });

    refreshDashboard();
  }, [router]);

  const refreshDashboard = async () => {
    if (refreshInFlight.current) {
      console.warn("[dashboard] refresh skipped because another refresh is in flight");
      return;
    }
    refreshInFlight.current = true;
    try {
      console.warn("[dashboard] refresh start");
      const [approvalData, scheduleData, taskData] = await Promise.all([
        listApprovals(),
        listSchedules(),
        listTasks(),
      ]);
      console.warn("[dashboard] refresh success", {
        approvals: approvalData.approvals.length,
        schedules: scheduleData.schedules.length,
        tasks: taskData.tasks.length,
        scheduleIds: scheduleData.schedules.map((schedule) => schedule.schedule_id),
      });
      setAuthExpired(false);
      setApprovals(approvalData.approvals);
      setSchedules(scheduleData.schedules);
      setTasks(taskData.tasks);
    } catch (error) {
      console.error("[dashboard] refresh failed", error);
      if (error instanceof UnauthorizedError) {
        setAuthExpired(true);
      }
    } finally {
      refreshInFlight.current = false;
    }
  };

  useEffect(() => {
    const timer = window.setInterval(() => {
      refreshDashboard();
    }, 5000);

    return () => window.clearInterval(timer);
  }, []);

  const handleSubmit = async (text: string) => {
    setLoading(true);
    try {
      const initial = await sendCommand(text);
      setTasks((prev) => [initial, ...prev.filter((task) => task.task_id !== initial.task_id)]);

      const final = await pollUntilDone(initial.task_id, (updated) => {
        setTasks((prev) => prev.map((task) => (task.task_id === updated.task_id ? updated : task)));
      });
      setTasks((prev) => prev.map((task) => (task.task_id === final.task_id ? final : task)));
      await refreshDashboard();
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const performDeleteTask = async (taskId: string) => {
    setDeletingTaskId(taskId);
    try {
      console.warn("[history] delete start", { taskId });
      await deleteTask(taskId);
      console.warn("[history] delete api success", { taskId });
      setTasks((prev) => prev.filter((task) => task.task_id !== taskId));
      console.warn("[history] delete state updated", { taskId });
      await refreshDashboard();
    } catch (error) {
      console.error("[history] delete failed", { taskId, error });
    } finally {
      console.warn("[history] delete finished", { taskId });
      setDeletingTaskId(null);
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    console.warn("[history] delete dialog open", { taskId });
    setConfirmAction({ kind: "delete-one", taskId });
  };

  const handleRetryTask = async (taskId: string) => {
    setRetryingTaskId(taskId);
    try {
      const retried = await retryTask(taskId);
      setTasks((prev) => [retried, ...prev]);
      const final = await pollUntilDone(retried.task_id, (updated) => {
        setTasks((prev) => prev.map((task) => (task.task_id === updated.task_id ? updated : task)));
      });
      setTasks((prev) => prev.map((task) => (task.task_id === final.task_id ? final : task)));
      await refreshDashboard();
    } catch (error) {
      console.error(error);
    } finally {
      setRetryingTaskId(null);
    }
  };

  const handleContinueWithAi = async (taskId: string) => {
    setContinuingAiTaskId(taskId);
    try {
      const updated = await continueTaskWithAi(taskId);
      setTasks((prev) => prev.map((task) => (task.task_id === updated.task_id ? updated : task)));
      await refreshDashboard();
    } catch (error) {
      console.error(error);
    } finally {
      setContinuingAiTaskId(null);
    }
  };

  const performDeleteSelected = async (taskIds: string[]) => {
    setBulkDeleting(true);
    try {
      console.warn("[history] bulk delete start", { taskIds });
      await deleteTasks(taskIds);
      console.warn("[history] bulk delete api success", { taskIds });
      setTasks((prev) => prev.filter((task) => !taskIds.includes(task.task_id)));
      setSelectedCompletedTaskIds((prev) => prev.filter((taskId) => !taskIds.includes(taskId)));
      console.warn("[history] bulk delete state updated", { taskIds });
      await refreshDashboard();
    } catch (error) {
      console.error("[history] bulk delete failed", { taskIds, error });
    } finally {
      console.warn("[history] bulk delete finished", { taskIds });
      setBulkDeleting(false);
    }
  };

  const handleDeleteSelected = async (taskIds: string[]) => {
    if (taskIds.length === 0) return;
    console.warn("[history] bulk delete dialog open", { taskIds });
    setConfirmAction({ kind: "delete-many", taskIds });
  };

  const confirmDialogTitle =
    confirmAction?.kind === "delete-many" ? t("delete_selected") : t("delete");
  const confirmDialogDescription =
    confirmAction?.kind === "delete-many"
      ? `${confirmAction.taskIds.length}${t("completed_history")}${t("delete_selected")}?`
      : t("delete");
  const confirmDialogLoading =
    confirmAction?.kind === "delete-many" ? bulkDeleting : deletingTaskId !== null;

  const handleConfirmAction = async () => {
    if (!confirmAction) return;
    console.warn("[history] confirm dialog accepted", confirmAction);
    if (confirmAction.kind === "delete-one") {
      const taskId = confirmAction.taskId;
      setConfirmAction(null);
      await performDeleteTask(taskId);
      return;
    }

    const taskIds = confirmAction.taskIds;
    setConfirmAction(null);
    await performDeleteSelected(taskIds);
  };

  const toggleCompletedTaskSelection = (taskId: string) => {
    setSelectedCompletedTaskIds((prev) =>
      prev.includes(taskId) ? prev.filter((id) => id !== taskId) : [...prev, taskId]
    );
  };

  const activeTasks = tasks.filter((task) =>
    ["pending", "running", "approval_required"].includes(task.status)
  );
  const completedTasks = tasks.filter((task) =>
    ["done", "failed", "cancelled"].includes(task.status)
  );
  const failedTasks = completedTasks.filter((task) => task.status === "failed");
  const completedTasksByCategory = {
    all: completedTasks,
    done: completedTasks.filter((task) => task.status === "done"),
    failed: completedTasks.filter((task) => task.status === "failed"),
    cancelled: completedTasks.filter((task) => task.status === "cancelled"),
  };
  const visibleCompletedTasks = completedTasksByCategory[completedFilter];
  const selectedVisibleCompletedTaskIds = selectedCompletedTaskIds.filter((taskId) =>
    visibleCompletedTasks.some((task) => task.task_id === taskId)
  );
  const upcomingSchedules = [...schedules]
    .filter((schedule) => Boolean(schedule.next_run_at))
    .sort((a, b) => {
      const left = a.next_run_at ? new Date(a.next_run_at).getTime() : Number.MAX_SAFE_INTEGER;
      const right = b.next_run_at ? new Date(b.next_run_at).getTime() : Number.MAX_SAFE_INTEGER;
      return left - right;
    })
    .slice(0, 3);
  const recentActivity = [...tasks].slice(0, 10);
  const scheduleHistory = schedules
    .map((schedule) => ({
      schedule,
      recentRuns: tasks.filter((task) => task.command === schedule.command).slice(0, 3),
    }))
    .filter((entry) => entry.recentRuns.length > 0)
    .slice(0, 3);

  console.warn("[dashboard] schedule state snapshot", {
    schedules: schedules.length,
    scheduleIds: schedules.map((schedule) => schedule.schedule_id),
    upcomingSchedules: upcomingSchedules.length,
    scheduleHistory: scheduleHistory.length,
    activeTab,
    isLocalUi,
  });

  const formatDateTime = (value: string | null) => {
    if (!value) return t("not_scheduled", "TBD");
    try {
      return new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      }).format(new Date(value));
    } catch {
      return value;
    }
  };

  const mobileStatusLabel =
    cloudflaredInstalled === false
      ? t("not_ready")
      : tunnelActive === true
        ? t("connected_short")
        : t("disconnected_short");
  const aiStatusLabel =
    aiVerified === true
      ? t("connected_short")
      : aiConfigured === true
        ? t("ready_short")
        : t("not_set_short");
  const mobileStatusTone =
    cloudflaredInstalled === false
      ? "border-amber-200 bg-amber-50 text-amber-800"
      : tunnelActive === true
        ? "border-emerald-200 bg-emerald-50 text-emerald-800"
        : "border-slate-200 bg-slate-100 text-slate-700";
  const aiStatusTone =
    aiVerified === true
      ? "border-violet-200 bg-violet-50 text-violet-800"
      : aiConfigured === true
        ? "border-amber-200 bg-amber-50 text-amber-800"
        : "border-slate-200 bg-slate-100 text-slate-700";

  const tabs = [
    { key: "execute" as const, label: t("execution_area") },
    { key: "routines" as const, label: t("operations_and_routines") },
    { key: "recent" as const, label: t("history_short") },
  ];

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.08),_transparent_28%),linear-gradient(to_bottom,_#f8fafc,_#f3f4f6)] px-4 py-5 md:py-7">
      <div className="mx-auto w-full max-w-5xl space-y-4">
        <section className="rounded-3xl border border-gray-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between gap-4">
            <div className="flex min-w-0 items-center gap-4">
              <img
                src="/sigorjob.png"
                alt="Sigorjob logo"
                className="h-20 w-20 shrink-0 rounded-[1.75rem] border border-gray-200 bg-white object-contain p-2 shadow-sm"
              />
              <div className="min-w-0">
                <h1 className="truncate text-3xl font-semibold tracking-tight text-gray-950">Sigorjob</h1>
                <p className="truncate text-sm text-gray-500">Automation for everyone. AI only when needed.</p>
              </div>
            </div>

            <div className="flex shrink-0 items-center gap-2">
              <LanguageToggle />
              {isLocalUi && (
                <CircleIconButton label={t("mobile_connection")} onClick={() => router.push("/pair")}>
                  <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current stroke-[1.8]">
                    <rect x="7" y="2.5" width="10" height="19" rx="2.5" />
                    <path d="M10 5.5h4" />
                    <path d="M11 18.5h2" />
                  </svg>
                </CircleIconButton>
              )}
              {isLocalUi && (
                <CircleIconButton label={t("settings")} onClick={() => router.push("/setup?source=settings")}>
                  <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current stroke-[1.8]">
                    <path d="M12 8.25A3.75 3.75 0 1 0 12 15.75A3.75 3.75 0 1 0 12 8.25Z" />
                    <path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a2 2 0 1 1-4 0v-.2a1 1 0 0 0-.7-.9 1 1 0 0 0-1.1.2l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a2 2 0 1 1 0-4h.2a1 1 0 0 0 .9-.7 1 1 0 0 0-.2-1.1l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1 1 0 0 0 1.1.2 1 1 0 0 0 .6-.9V4a2 2 0 1 1 4 0v.2a1 1 0 0 0 .7.9 1 1 0 0 0 1.1-.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1 1 0 0 0-.2 1.1 1 1 0 0 0 .9.6H20a2 2 0 1 1 0 4h-.2a1 1 0 0 0-.9.7Z" />
                  </svg>
                </CircleIconButton>
              )}
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2 rounded-2xl border border-gray-100 bg-gray-50 px-3 py-2">
            <button
              type="button"
              onClick={() => setInfoModal("mobile")}
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${mobileStatusTone}`}
            >
              <span>{t("mobile_connection", "Mobile Connect")}: {mobileStatusLabel}</span>
              <span className="flex h-4 w-4 items-center justify-center rounded-full border border-current text-[10px]">!</span>
            </button>
            <button
              type="button"
              onClick={() => setInfoModal("ai")}
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${aiStatusTone}`}
            >
              <span>AI: {aiStatusLabel}</span>
              <span className="flex h-4 w-4 items-center justify-center rounded-full border border-current text-[10px]">!</span>
            </button>
          </div>
        </section>

        {authExpired && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-4">
            <p className="text-sm font-semibold text-red-900">{t("mobile_auth_expired")}</p>
            <p className="mt-1 text-sm leading-6 text-red-800">{t("mobile_auth_expired_desc")}</p>
          </div>
        )}

        <section className="grid grid-cols-3 gap-3">
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3">
            <p className="text-[11px] text-amber-700">{t("pending_actions")}</p>
            <p className="mt-1 text-lg font-semibold text-amber-950">{activeTasks.length + approvals.length}</p>
          </div>
          <div className="rounded-2xl border border-sky-200 bg-sky-50 p-3">
            <p className="text-[11px] text-sky-700">{t("routine_count")}</p>
            <p className="mt-1 text-lg font-semibold text-sky-950">{schedules.length}</p>
          </div>
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-3">
            <p className="text-[11px] text-rose-700">{t("recent_failures")}</p>
            <p className="mt-1 text-lg font-semibold text-rose-950">{failedTasks.length}</p>
          </div>
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white p-2 shadow-sm">
          <div className="flex flex-wrap gap-2">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  activeTab === tab.key
                    ? "bg-gray-900 text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </section>

        {activeTab === "execute" && (
          <section className="space-y-4">
            <section className="grid gap-4 xl:grid-cols-[1.35fr_0.65fr]">
            <div className="space-y-4">
              <section className="rounded-3xl border border-gray-200 bg-white p-4 shadow-sm">
                <h2 className="text-sm font-semibold text-gray-950">{t("control_center")}</h2>
                <div className="mt-3">
                  <CommandInput onSubmit={handleSubmit} loading={loading} />
                </div>
                <div className="mt-3 space-y-3">
                  {activeTasks.map((task) => (
                    <TaskCard
                      key={task.task_id}
                      task={task}
                      onDelete={handleDeleteTask}
                      deleting={deletingTaskId === task.task_id}
                      onRetry={handleRetryTask}
                      retrying={retryingTaskId === task.task_id}
                      onContinueWithAi={handleContinueWithAi}
                      continuingWithAi={continuingAiTaskId === task.task_id}
                    />
                  ))}
                  {activeTasks.length === 0 && (
                    <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 p-4 text-sm text-gray-500">
                      {completedTasks.length === 0
                        ? t("no_history")
                        : t("no_active_tasks")}
                    </div>
                  )}
                </div>
              </section>

              <section className="rounded-3xl border border-gray-200 bg-white p-4 shadow-sm">
                <h2 className="text-sm font-semibold text-gray-950">{t("approval_and_queue")}</h2>
                <div className="mt-3">
                  <ApprovalPanel approvals={approvals} onResolved={refreshDashboard} />
                </div>
              </section>

              <button
                type="button"
                onClick={() => setActiveTab("recent")}
                className="block w-full rounded-3xl border border-gray-200 bg-white p-4 text-left shadow-sm transition hover:border-blue-200 hover:bg-blue-50/30"
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold text-gray-950">
                    {t("recent_history")}
                  </span>
                  <span className="text-xs text-gray-500">
                    {completedTasksByCategory.done.length}{t("done_suffix")} / {failedTasks.length}{t("failed_suffix")}
                  </span>
                </div>
                <div className="mt-3 space-y-2">
                  {recentActivity.length > 0 ? (
                    recentActivity.map((task) => (
                      <div
                        key={`mini-${task.task_id}`}
                        className="block w-full rounded-2xl border border-gray-100 bg-gray-50 px-4 py-3 text-left"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="truncate text-sm font-medium text-gray-900">{task.command || t("run")}</p>
                            <p className="mt-1 text-xs leading-5 text-gray-500">
                              {task.result?.summary || t("pending")}
                            </p>
                          </div>
                          <span className="shrink-0 rounded-full bg-white px-2 py-1 text-[11px] font-medium text-gray-600">
                            {task.status}
                          </span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-gray-500">{t("no_history")}</p>
                  )}
                </div>
              </button>
            </div>

            <div />
          </section>
          </section>
        )}

        {activeTab === "routines" && (
          <section className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
            <div>
              {isLocalUi && <SchedulePanel schedules={schedules} onChanged={refreshDashboard} />}
            </div>

            <section className="rounded-3xl border border-gray-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-semibold text-gray-950">{t("routine_overview")}</h2>
              <div className="mt-3 space-y-3">
                <div className="space-y-3">
                  {upcomingSchedules.length > 0 ? (
                    upcomingSchedules.map((schedule) => (
                      <div key={schedule.schedule_id} className="rounded-2xl border border-emerald-100 bg-emerald-50 p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="text-sm font-semibold text-emerald-950">{schedule.name}</p>
                            <p className="mt-1 text-xs font-mono text-emerald-700">{schedule.cron}</p>
                          </div>
                          <span className="rounded-full bg-white/80 px-2 py-1 text-[11px] font-medium text-emerald-700">
                            {schedule.status}
                          </span>
                        </div>
                        <p className="mt-3 text-xs text-emerald-800">
                          {t("next_run")}: {formatDateTime(schedule.next_run_at)}
                        </p>
                      </div>
                    ))
                  ) : (
                    <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 p-4 text-sm text-gray-500">
                      {t("routine_empty_desc")}
                    </div>
                  )}
                </div>

                <div className="rounded-2xl border border-gray-100 bg-gray-50 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-semibold text-gray-900">{t("routine_history")}</p>
                    <span className="text-xs text-gray-500">{scheduleHistory.length}</span>
                  </div>
                  {scheduleHistory.length > 0 ? (
                    <div className="mt-3 space-y-2">
                      {scheduleHistory.map(({ schedule, recentRuns }) => (
                        <div key={`history-${schedule.schedule_id}`} className="rounded-2xl border border-white bg-white p-3">
                          <p className="text-sm font-medium text-gray-900">{schedule.name}</p>
                          <div className="mt-2 space-y-2">
                            {recentRuns.map((task) => (
                              <div key={`history-task-${task.task_id}`} className="flex items-center justify-between gap-3 text-xs">
                                <span className="truncate text-gray-600">{task.result?.summary || task.command}</span>
                                <span className="rounded-full bg-gray-50 px-2 py-1 text-gray-500">{task.status}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="mt-3 rounded-2xl border border-dashed border-gray-200 bg-white p-4 text-sm text-gray-500">
                      {t("routine_history_empty")}
                    </div>
                  )}
                </div>
              </div>
            </section>
          </section>
        )}

        {activeTab === "recent" && (
          <section className="rounded-3xl border border-gray-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-semibold text-gray-950">{t("history_short")}</h2>
              {completedTasks.length > 0 ? (
                <div className="mt-3 space-y-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="flex flex-wrap gap-2">
                      {(
                        [
                          ["all", t("all")],
                          ["done", t("done")],
                          ["failed", t("failed")],
                          ["cancelled", t("cancelled")],
                        ] as const
                      ).map(([key, label]) => (
                        <button
                          key={key}
                          onClick={() => setCompletedFilter(key)}
                          className={`rounded-full px-3 py-1.5 text-xs font-medium ${
                            completedFilter === key
                              ? "bg-blue-600 text-white"
                              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                          }`}
                        >
                          {label} {completedTasksByCategory[key].length}
                        </button>
                      ))}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        onClick={() =>
                          setSelectedCompletedTaskIds(
                            selectedVisibleCompletedTaskIds.length === visibleCompletedTasks.length &&
                              visibleCompletedTasks.length > 0
                              ? []
                              : Array.from(
                                  new Set([
                                    ...selectedCompletedTaskIds,
                                    ...visibleCompletedTasks.map((task) => task.task_id),
                                  ])
                                )
                          )
                        }
                        className="rounded-full border border-gray-200 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50"
                      >
                        {selectedVisibleCompletedTaskIds.length === visibleCompletedTasks.length &&
                        visibleCompletedTasks.length > 0
                          ? t("deselect")
                          : t("select_all")}
                      </button>
                      <button
                        onClick={() => handleDeleteSelected(selectedVisibleCompletedTaskIds)}
                        disabled={selectedVisibleCompletedTaskIds.length === 0 || bulkDeleting}
                        className="rounded-full bg-gray-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
                      >
                        {bulkDeleting
                          ? t("deleting")
                          : `${t("delete_selected")}${selectedVisibleCompletedTaskIds.length > 0 ? ` (${selectedVisibleCompletedTaskIds.length})` : ""}`}
                      </button>
                    </div>
                  </div>

                  {completedFilter === "failed" && completedTasksByCategory.failed.length > 0 && (
                    <div className="rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                      {t("failures_only_desc")}
                    </div>
                  )}

                  <div className="space-y-3">
                    {visibleCompletedTasks.map((task) => (
                      <TaskCard
                        key={task.task_id}
                        task={task}
                        onDelete={handleDeleteTask}
                        deleting={deletingTaskId === task.task_id}
                        onRetry={handleRetryTask}
                        retrying={retryingTaskId === task.task_id}
                        onContinueWithAi={handleContinueWithAi}
                        continuingWithAi={continuingAiTaskId === task.task_id}
                        selectable
                        selected={selectedCompletedTaskIds.includes(task.task_id)}
                        onToggleSelect={toggleCompletedTaskSelection}
                      />
                    ))}
                    {visibleCompletedTasks.length === 0 && (
                      <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 p-4 text-sm text-gray-500">
                        {t("no_items_in_category")}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="mt-4 rounded-2xl border border-dashed border-gray-200 bg-gray-50 p-4 text-sm text-gray-500">
                  {t("no_history")}
                </div>
              )}
          </section>
        )}

      {infoModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 p-4">
            <div className="w-full max-w-sm rounded-3xl bg-white p-5 shadow-2xl">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-base font-semibold text-gray-950">
                    {infoModal === "mobile" ? t("mobile_connection") : "AI"}
                  </h2>
                  <p className="mt-1 text-sm text-gray-600">
                    {infoModal === "mobile"
                      ? mobileStatusLabel
                      : aiStatusLabel}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setInfoModal(null)}
                  className="rounded-full bg-gray-100 px-2.5 py-1 text-sm text-gray-600 hover:bg-gray-200"
                >
                  {t("close")}
                </button>
              </div>

              <div className="mt-4 space-y-3 text-sm leading-6 text-gray-600">
                {infoModal === "mobile" ? (
                  <>
                    <div className="grid gap-3">
                      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-3">
                        <p className="text-sm font-semibold text-emerald-900">{t("connected_short")}</p>
                        <p className="mt-1 text-sm text-emerald-800">{t("mobile_ready_desc")}</p>
                      </div>
                      <div className="rounded-2xl border border-slate-200 bg-slate-100 p-3">
                        <p className="text-sm font-semibold text-slate-900">{t("disconnected_short")}</p>
                        <p className="mt-1 text-sm text-slate-700">{t("mobile_off_desc")}</p>
                      </div>
                      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3">
                        <p className="text-sm font-semibold text-amber-900">{t("not_ready")}</p>
                        <p className="mt-1 text-sm text-amber-800">{t("mobile_component_desc")}</p>
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="grid gap-3">
                      <div className="rounded-2xl border border-violet-200 bg-violet-50 p-3">
                        <p className="text-sm font-semibold text-violet-900">{t("connected_short")}</p>
                        <p className="mt-1 text-sm text-violet-800">{t("ai_verified_desc")}</p>
                      </div>
                      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3">
                        <p className="text-sm font-semibold text-amber-900">{t("ready_short")}</p>
                        <p className="mt-1 text-sm text-amber-800">{t("ai_key_saved_not_verified")}</p>
                      </div>
                      <div className="rounded-2xl border border-slate-200 bg-slate-100 p-3">
                        <p className="text-sm font-semibold text-slate-900">{t("not_set_short")}</p>
                        <p className="mt-1 text-sm text-slate-700">{t("ai_not_set_desc")}</p>
                      </div>
                    </div>
                    {aiValidationError && (
                      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-amber-900">
                        {aiValidationError}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        <ConfirmDialog
          open={Boolean(confirmAction)}
          title={confirmDialogTitle}
          description={confirmDialogDescription}
          confirmLabel={t("delete")}
          cancelLabel={t("close")}
          loading={confirmDialogLoading}
          onCancel={() => {
            console.warn("[history] confirm dialog cancelled", confirmAction);
            setConfirmAction(null);
          }}
          onConfirm={handleConfirmAction}
        />
      </div>
    </main>
  );
}

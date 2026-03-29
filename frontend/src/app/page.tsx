"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import ApprovalPanel from "@/components/ApprovalPanel";
import CommandInput from "@/components/CommandInput";
import LanguageToggle from "@/components/LanguageToggle";
import { useLanguage } from "@/components/LanguageProvider";
import SchedulePanel from "@/components/SchedulePanel";
import TaskCard from "@/components/TaskCard";
import {
  ApprovalItem,
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

export default function Home() {
  const router = useRouter();
  const { t } = useLanguage();
  const [tasks, setTasks] = useState<TaskResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [tunnelActive, setTunnelActive] = useState<boolean | null>(null);
  const [cloudflaredInstalled, setCloudflaredInstalled] = useState<boolean | null>(null);
  const [isLocalUi, setIsLocalUi] = useState(false);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [schedules, setSchedules] = useState<ScheduleItem[]>([]);
  const [deletingTaskId, setDeletingTaskId] = useState<string | null>(null);
  const [retryingTaskId, setRetryingTaskId] = useState<string | null>(null);
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [authExpired, setAuthExpired] = useState(false);
  const [showSetupDialog, setShowSetupDialog] = useState(false);
  const [selectedCompletedTaskIds, setSelectedCompletedTaskIds] = useState<string[]>([]);
  const [completedFilter, setCompletedFilter] = useState<"all" | "done" | "failed" | "cancelled">("all");
  const [aiConfigured, setAiConfigured] = useState<boolean | null>(null);

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
        if (!data.configured) {
          setShowSetupDialog(true);
        }
      })
      .catch(() => {
        // ignore local bootstrap failures
      });

    refreshDashboard();
  }, [router]);

  const refreshDashboard = async () => {
    try {
      const [approvalData, scheduleData, taskData] = await Promise.all([
        listApprovals(),
        listSchedules(),
        listTasks(),
      ]);
      setAuthExpired(false);
      setApprovals(approvalData.approvals);
      setSchedules(scheduleData.schedules);
      setTasks(taskData.tasks);
    } catch (error) {
      if (error instanceof UnauthorizedError) {
        setAuthExpired(true);
      }
    }
  };

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

  const handleDeleteTask = async (taskId: string) => {
    if (typeof window !== "undefined") {
      const confirmed = window.confirm(`${t("delete")} ?`);
      if (!confirmed) return;
    }

    setDeletingTaskId(taskId);
    try {
      await deleteTask(taskId);
      setTasks((prev) => prev.filter((task) => task.task_id !== taskId));
      await refreshDashboard();
    } catch (error) {
      console.error(error);
    } finally {
      setDeletingTaskId(null);
    }
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

  const handleDeleteSelected = async (taskIds: string[]) => {
    if (taskIds.length === 0) return;
    if (typeof window !== "undefined") {
      const confirmed = window.confirm(`${t("delete_selected")} ${taskIds.length}?`);
      if (!confirmed) return;
    }

    setBulkDeleting(true);
    try {
      await deleteTasks(taskIds);
      setTasks((prev) => prev.filter((task) => !taskIds.includes(task.task_id)));
      setSelectedCompletedTaskIds((prev) => prev.filter((taskId) => !taskIds.includes(taskId)));
      await refreshDashboard();
    } catch (error) {
      console.error(error);
    } finally {
      setBulkDeleting(false);
    }
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
  const recentActivity = [...tasks].slice(0, 5);
  const scheduleHistory = schedules
    .map((schedule) => ({
      schedule,
      recentRuns: tasks
        .filter((task) => task.command === schedule.command)
        .slice(0, 3),
    }))
    .filter((entry) => entry.recentRuns.length > 0)
    .slice(0, 3);

  const formatDateTime = (value: string | null) => {
    if (!value) return t("not_scheduled", "미정");
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

  const stats = [
    {
      label: t("routine_count", "등록된 루틴"),
      value: schedules.length,
      tone: "border-sky-200 bg-sky-50 text-sky-950",
      sub:
        schedules.length > 0
          ? t("routine_count_desc", "반복 실행할 작업이 준비되어 있습니다.")
          : t("routine_empty_desc", "아직 등록된 루틴이 없습니다."),
    },
    {
      label: t("next_runs", "곧 실행될 루틴"),
      value: upcomingSchedules.length,
      tone: "border-emerald-200 bg-emerald-50 text-emerald-950",
      sub: upcomingSchedules[0]?.name || t("next_runs_desc", "다음 실행 예정 루틴이 없습니다."),
    },
    {
      label: t("pending_actions", "처리 중인 작업"),
      value: activeTasks.length + approvals.length,
      tone: "border-amber-200 bg-amber-50 text-amber-950",
      sub:
        approvals.length > 0
          ? `${approvals.length}${t("approval_waiting_suffix", "건 승인 대기")}`
          : t("pending_actions_desc", "지금은 대기 중인 작업이 많지 않습니다."),
    },
    {
      label: t("recent_failures", "최근 실패"),
      value: failedTasks.length,
      tone: "border-rose-200 bg-rose-50 text-rose-950",
      sub:
        failedTasks.length > 0
          ? t("recent_failures_desc", "실패 내역을 따로 보고 정리할 수 있습니다.")
          : t("recent_failures_clear", "최근 실패 내역이 없습니다."),
    },
  ];

  return (
    <main className="min-h-screen bg-gray-50 px-4 py-10">
      <div className="mx-auto w-full max-w-6xl space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Sigorjob</h1>
            <p className="mt-1 text-sm text-gray-500">
              {t("dashboard_desc", "루틴, 최근 실행, 모바일 연결 상태를 한 화면에서 관리합니다.")}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <LanguageToggle />
            {cloudflaredInstalled === false && (
              <button
                onClick={() => setShowSetupDialog(true)}
                className="rounded-full bg-red-50 px-3 py-1 text-xs font-medium text-red-600 hover:bg-red-100"
              >
                {t("mobile_connection_component_needed")}
              </button>
            )}
            {tunnelActive === false && (
              <button
                onClick={() => setShowSetupDialog(true)}
                className="rounded-full bg-orange-50 px-3 py-1 text-xs font-medium text-orange-600 hover:bg-orange-100"
              >
                {t("mobile_connection_off")}
              </button>
            )}
            {tunnelActive === true && (
              <button
                onClick={() => setShowSetupDialog(true)}
                className="rounded-full bg-green-50 px-3 py-1 text-xs font-medium text-green-600 hover:bg-green-100"
              >
                {t("mobile_connection_on")}
              </button>
            )}
            {aiConfigured === true && (
              <button
                onClick={() => setShowSetupDialog(true)}
                className="rounded-full bg-blue-50 px-3 py-1 text-xs font-medium text-blue-600 hover:bg-blue-100"
              >
                {t("ai_connected")}
              </button>
            )}
            {aiConfigured === false && (
              <button
                onClick={() => setShowSetupDialog(true)}
                className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-600 hover:bg-gray-200"
              >
                {t("ai_not_set")}
              </button>
            )}
            {isLocalUi && (
              <>
                <a href="/pair" className="text-sm text-gray-500 hover:text-blue-600">
                  {t("mobile_connection")}
                </a>
                <button
                  onClick={() => setShowSetupDialog(true)}
                  className="text-sm text-gray-400 hover:text-gray-600"
                >
                  {t("settings")}
                </button>
              </>
            )}
          </div>
        </div>

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {stats.map((stat) => (
            <div key={stat.label} className={`rounded-2xl border p-4 ${stat.tone}`}>
              <p className="text-xs font-medium opacity-80">{stat.label}</p>
              <p className="mt-2 text-3xl font-bold">{stat.value}</p>
              <p className="mt-2 text-xs leading-5 opacity-80">{stat.sub}</p>
            </div>
          ))}
        </section>

        {isLocalUi && tunnelActive !== true && (
          <button
            onClick={() => setShowSetupDialog(true)}
            className="w-full rounded-2xl border border-orange-200 bg-orange-50 p-4 text-left hover:bg-orange-100"
          >
            <p className="text-sm font-semibold text-orange-900">{t("mobile_connection_not_ready")}</p>
            <p className="mt-1 text-sm leading-6 text-orange-800">
              {t("mobile_connection_not_ready_desc")}
            </p>
            <p className="mt-2 text-xs text-orange-700">{t("choose_mobile_connection")}</p>
          </button>
        )}

        {authExpired && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-4">
            <p className="text-sm font-semibold text-red-900">{t("mobile_auth_expired")}</p>
            <p className="mt-1 text-sm leading-6 text-red-800">{t("mobile_auth_expired_desc")}</p>
          </div>
        )}

        <section className="grid gap-6 xl:grid-cols-[1.35fr_0.95fr]">
          <div className="space-y-6">
            <section className="rounded-2xl border border-gray-200 bg-white p-4 md:p-5 space-y-4">
              <div>
                <h2 className="text-sm font-semibold text-gray-900">
                  {t("control_center", "실행 센터")}
                </h2>
                <p className="text-xs text-gray-500">
                  {t("control_center_desc", "새 명령을 실행하고 현재 진행 중인 작업을 바로 확인합니다.")}
                </p>
              </div>
              <CommandInput onSubmit={handleSubmit} loading={loading} />
              <div className="space-y-3">
                {activeTasks.map((task) => (
                  <TaskCard
                    key={task.task_id}
                    task={task}
                    onDelete={handleDeleteTask}
                    deleting={deletingTaskId === task.task_id}
                    onRetry={handleRetryTask}
                    retrying={retryingTaskId === task.task_id}
                  />
                ))}
                {activeTasks.length === 0 && completedTasks.length === 0 && (
                  <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50 p-5 text-sm text-gray-500">
                    {t("no_history")}
                  </div>
                )}
                {activeTasks.length === 0 && completedTasks.length > 0 && (
                  <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50 p-5 text-sm text-gray-500">
                    {t("no_active_tasks", "지금 실행 중이거나 승인 대기인 작업이 없습니다.")}
                  </div>
                )}
              </div>
            </section>

            <ApprovalPanel approvals={approvals} onResolved={refreshDashboard} />

            {completedTasks.length > 0 && (
              <section className="rounded-2xl border border-gray-200 bg-white p-4 md:p-5 space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-gray-900">
                      {t("completed_history")} {completedTasks.length}
                    </p>
                    <p className="text-xs text-gray-500">
                      {t("history_mgmt_desc", "최근 결과를 상태별로 확인하고 필요한 내역만 선택해서 정리할 수 있습니다.")}
                    </p>
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

                {completedFilter === "failed" && completedTasksByCategory.failed.length > 0 && (
                  <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">
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
                      selectable
                      selected={selectedCompletedTaskIds.includes(task.task_id)}
                      onToggleSelect={toggleCompletedTaskSelection}
                    />
                  ))}
                  {visibleCompletedTasks.length === 0 && (
                    <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50 p-5 text-sm text-gray-500">
                      {t("no_items_in_category")}
                    </div>
                  )}
                </div>
              </section>
            )}
          </div>

          <div className="space-y-6">
            {isLocalUi && <SchedulePanel schedules={schedules} onChanged={refreshDashboard} />}

            <section className="rounded-2xl border border-gray-200 bg-white p-4 md:p-5 space-y-4">
              <div>
                <h2 className="text-sm font-semibold text-gray-900">
                  {t("routine_overview", "루틴 관리 요약")}
                </h2>
                <p className="text-xs text-gray-500">
                  {t("routine_overview_desc", "다음 실행 예정 루틴과 최근 실행 상태를 빠르게 확인합니다.")}
                </p>
              </div>

              <div className="space-y-3">
                {upcomingSchedules.length > 0 ? (
                  upcomingSchedules.map((schedule) => (
                    <div key={schedule.schedule_id} className="rounded-xl border border-emerald-100 bg-emerald-50 p-4">
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
                  <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50 p-5 text-sm text-gray-500">
                    {t("routine_empty_desc", "아직 등록된 루틴이 없습니다.")}
                  </div>
                )}
              </div>

              <div className="rounded-xl border border-gray-100 bg-white p-4 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-gray-900">
                    {t("routine_history", "루틴 최근 실행")}
                  </p>
                  <span className="text-xs text-gray-500">{scheduleHistory.length}</span>
                </div>
                {scheduleHistory.length > 0 ? (
                  <div className="space-y-3">
                    {scheduleHistory.map(({ schedule, recentRuns }) => (
                      <div key={`history-${schedule.schedule_id}`} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                        <p className="text-sm font-medium text-gray-900">{schedule.name}</p>
                        <div className="mt-2 space-y-2">
                          {recentRuns.map((task) => (
                            <div key={`history-task-${task.task_id}`} className="flex items-center justify-between gap-3 text-xs">
                              <span className="truncate text-gray-600">{task.result?.summary || task.command}</span>
                              <span className="rounded-full bg-white px-2 py-1 text-gray-500">{task.status}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50 p-4 text-sm text-gray-500">
                    {t("routine_history_empty", "아직 루틴 실행 내역이 충분히 쌓이지 않았습니다.")}
                  </div>
                )}
              </div>

              <div className="rounded-xl border border-gray-100 bg-gray-50 p-4 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-gray-900">
                    {t("recent_activity", "최근 실행 요약")}
                  </p>
                  <span className="text-xs text-gray-500">
                    {completedTasksByCategory.done.length}{t("done_suffix", "건 완료")} / {failedTasks.length}{t("failed_suffix", "건 실패")}
                  </span>
                </div>
                <div className="space-y-2">
                  {recentActivity.length > 0 ? (
                    recentActivity.map((task) => (
                      <div
                        key={`mini-${task.task_id}`}
                        className="flex items-start justify-between gap-3 rounded-lg bg-white px-3 py-2"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm text-gray-900">{task.command || t("run")}</p>
                          <p className="mt-1 text-xs text-gray-500">
                            {task.result?.summary || t("pending")}
                          </p>
                        </div>
                        <span className="shrink-0 rounded-full bg-gray-100 px-2 py-1 text-[11px] font-medium text-gray-600">
                          {task.status}
                        </span>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-gray-500">{t("no_history")}</p>
                  )}
                </div>
              </div>
            </section>
          </div>
        </section>
      </div>

      {showSetupDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-5 shadow-xl space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold text-gray-900">
                  {t("remote_connection_setup")}
                </h2>
                <p className="mt-1 text-sm text-gray-500">
                  {t("remote_connection_setup_desc")}
                </p>
              </div>
              <button
                onClick={() => setShowSetupDialog(false)}
                className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-600 hover:bg-gray-200"
              >
                {t("close_label")}
              </button>
            </div>

            <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 space-y-2">
              <p className="text-xs font-medium text-gray-500">{t("current_status")}</p>
              <p className="text-sm font-medium text-gray-900">
                {tunnelActive
                  ? t("tunnel_connected_desc")
                  : t("no_remote_mode_desc")}
              </p>
              {aiConfigured === true && (
                <p className="text-xs text-gray-500">{t("ai_key_saved")}</p>
              )}
              {aiConfigured === false && (
                <p className="text-xs text-gray-500">{t("ai_key_not_set")}</p>
              )}
            </div>

            <div className="grid gap-2">
              <button
                onClick={() => router.push("/setup")}
                className="w-full rounded-xl bg-blue-600 px-4 py-3 text-sm font-medium text-white hover:bg-blue-700"
              >
                {t("open_connection_setup")}
              </button>
              {isLocalUi && (
                <button
                  onClick={() => router.push("/pair")}
                  className="w-full rounded-xl border border-gray-200 px-4 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50"
                >
                  {t("open_mobile_pair")}
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

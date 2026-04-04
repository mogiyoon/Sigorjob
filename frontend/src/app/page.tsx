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
  approveTask,
  continueTaskWithAi,
  deleteTask,
  deleteTasks,
  getBaseUrl,
  getSetupStatus,
  getTask,
  listApprovals,
  listSchedules,
  listTasks,
  rejectTask,
  retryTask,
  ScheduleItem,
  sendCommand,
  TaskResponse,
  UnauthorizedError,
} from "@/lib/api";

type DashboardTab = "execute" | "routines" | "recent";

interface ApprovalModalState {
  taskId: string;
  command: string;
  riskLevel: string;
  reason: string | null;
}

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
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [backendStartupError, setBackendStartupError] = useState<string | null>(null);
  const [backendStartupLogPath, setBackendStartupLogPath] = useState<string | null>(null);
  const [approvalModal, setApprovalModal] = useState<ApprovalModalState | null>(null);
  const [approvalActionLoading, setApprovalActionLoading] = useState<"approve" | "reject" | null>(null);
  const approvalDecisionResolverRef = useRef<((approved: boolean) => void) | null>(null);
  const [deleteDialog, setDeleteDialog] = useState<
    | { mode: "single"; taskId: string }
    | { mode: "bulk"; taskIds: string[] }
    | null
  >(null);

  const refreshRuntimeStatus = async () => {
    try {
      const data = await getSetupStatus();
      setTunnelActive(data.tunnel_active);
      setCloudflaredInstalled(data.cloudflared_installed);
      setAiConfigured(Boolean(data.ai_configured));
      setAiVerified(Boolean(data.ai_verified));
      setAiValidationError(data.ai_validation_error ?? null);
    } catch {
      // backend may still be starting when the desktop app first opens
    }
  };

  useEffect(() => {
    const localUi =
      typeof window !== "undefined" &&
      ["127.0.0.1", "localhost", "tauri.localhost"].includes(window.location.hostname);
    setIsLocalUi(localUi);
    if (typeof window !== "undefined") {
      const startupWindow = window as Window & {
        __SIGORJOB_STARTUP_ERROR?: string;
        __SIGORJOB_STARTUP_LOG_PATH?: string;
      };
      setBackendStartupError(startupWindow.__SIGORJOB_STARTUP_ERROR?.trim() || null);
      setBackendStartupLogPath(startupWindow.__SIGORJOB_STARTUP_LOG_PATH?.trim() || null);
    }

    if (!localUi) {
      refreshDashboard();
      return;
    }

    refreshRuntimeStatus();
    refreshDashboard();
    const interval = setInterval(() => {
      refreshRuntimeStatus();
      refreshDashboard();
    }, 3000);

    return () => clearInterval(interval);
  }, [router]);

  useEffect(() => {
    return () => {
      approvalDecisionResolverRef.current?.(false);
      approvalDecisionResolverRef.current = null;
    };
  }, []);

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
      if (isLocalUi) {
        await refreshRuntimeStatus();
      }
    } catch (error) {
      if (error instanceof UnauthorizedError) {
        setAuthExpired(true);
      }
    }
  };

  const upsertTask = (updated: TaskResponse) => {
    setTasks((prev) => {
      const existing = prev.some((task) => task.task_id === updated.task_id);
      if (!existing) {
        return [updated, ...prev];
      }
      return prev.map((task) => (task.task_id === updated.task_id ? updated : task));
    });
  };

  const waitForApprovalDecision = async (task: TaskResponse): Promise<boolean> => {
    let approval = approvals.find((item) => item.task_id === task.task_id) ?? null;
    if (!approval) {
      try {
        const approvalData = await listApprovals();
        setApprovals(approvalData.approvals);
        approval = approvalData.approvals.find((item) => item.task_id === task.task_id) ?? null;
      } catch {
        approval = null;
      }
    }

    setApprovalModal({
      taskId: task.task_id,
      command: approval?.command || task.command || t("run"),
      riskLevel: approval?.risk_level || "medium",
      reason: approval?.reason ?? null,
    });

    return new Promise<boolean>((resolve) => {
      approvalDecisionResolverRef.current = resolve;
    });
  };

  const pollTaskUntilSettled = async (taskId: string): Promise<TaskResponse> => {
    const startedAt = Date.now();

    while (Date.now() - startedAt < 60000) {
      const updated = await getTask(taskId);
      upsertTask(updated);

      if (
        updated.status === "done" ||
        updated.status === "failed" ||
        updated.status === "cancelled" ||
        updated.status === "needs_clarification"
      ) {
        return updated;
      }

      if (updated.status === "approval_required") {
        const approved = await waitForApprovalDecision(updated);
        if (!approved) {
          try {
            const rejected = await getTask(taskId);
            if (
              rejected.status === "done" ||
              rejected.status === "failed" ||
              rejected.status === "cancelled" ||
              rejected.status === "needs_clarification"
            ) {
              upsertTask(rejected);
              return rejected;
            }
          } catch {
            // Fall through to a local failed state when the backend state is not available yet.
          }

          const failedTask: TaskResponse = {
            ...updated,
            status: "failed",
            result: updated.result,
          };
          upsertTask(failedTask);
          return failedTask;
        }
      }

      await new Promise((resolve) => setTimeout(resolve, 1000));
    }

    throw new Error("polling timeout");
  };

  const handleSubmit = async (text: string) => {
    setLoading(true);
    setSubmitError(null);
    console.warn("[submit] start", {
      text,
      isLocalUi,
      baseUrl: getBaseUrl(),
    });
    try {
      const initial = await sendCommand(text);
      console.warn("[submit] initial task created", initial);
      upsertTask(initial);

      const final = await pollTaskUntilSettled(initial.task_id);
      console.warn("[submit] final task", final);
      upsertTask(final);
      await refreshDashboard();
      return true;
    } catch (error) {
      console.warn("[submit] failed", {
        text,
        error: error instanceof Error ? error.message : String(error),
      });
      console.error(error);
      if (error instanceof UnauthorizedError) {
        setSubmitError(t("submit_error_auth", "The connection expired. Reconnect and try again."));
      } else if (error instanceof Error) {
        setSubmitError(`${t("submit_error_generic", "Could not send the request. Please try again.")} (${error.message})`);
      } else {
        setSubmitError(t("submit_error_generic", "Could not send the request. Please try again."));
      }
      return false;
    } finally {
      setLoading(false);
    }
  };

  const handleClarificationAnswer = async (task: TaskResponse, answer: string) => {
    setLoading(true);
    try {
      const clarification = (task.result as { clarification?: unknown } | null)?.clarification ?? {};
      const nextTask = await sendCommand(answer, { clarification });
      setTasks((prev) => prev.filter((item) => item.task_id !== task.task_id && item.task_id !== nextTask.task_id));
      upsertTask(nextTask);

      const final = await pollTaskUntilSettled(nextTask.task_id);
      upsertTask(final);
      await refreshDashboard();
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteTask = async (taskId: string) => {
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
      upsertTask(retried);
      const final = await pollTaskUntilSettled(retried.task_id);
      upsertTask(final);
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

  const handleDeleteSelected = async (taskIds: string[]) => {
    if (taskIds.length === 0) return;
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
    ["pending", "running", "needs_clarification", "approval_required"].includes(task.status)
  );
  const completedTasks = tasks.filter((task) =>
    ["done", "failed", "cancelled"].includes(task.status)
  );
  const recentCompletedTasks = completedTasks.slice(0, 3);
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

  const approvalRiskTone =
    approvalModal?.riskLevel === "high"
      ? "border-red-200 bg-red-50 text-red-800"
      : approvalModal?.riskLevel === "medium"
        ? "border-amber-200 bg-amber-50 text-amber-800"
        : "border-emerald-200 bg-emerald-50 text-emerald-800";

  const handleApproveCurrentTask = async () => {
    if (!approvalModal) return;
    setApprovalActionLoading("approve");
    try {
      await approveTask(approvalModal.taskId);
      setApprovalModal(null);
      approvalDecisionResolverRef.current?.(true);
      approvalDecisionResolverRef.current = null;
      await refreshDashboard();
    } catch (error) {
      console.error(error);
    } finally {
      setApprovalActionLoading(null);
    }
  };

  const handleRejectCurrentTask = async () => {
    if (!approvalModal) return;
    setApprovalActionLoading("reject");
    try {
      await rejectTask(approvalModal.taskId);
      setSubmitError(t("task_rejected_message", "Approval was rejected. The task was cancelled."));
      setApprovalModal(null);
      approvalDecisionResolverRef.current?.(false);
      approvalDecisionResolverRef.current = null;
      await refreshDashboard();
    } catch (error) {
      console.error(error);
    } finally {
      setApprovalActionLoading(null);
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
      {approvalModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/45 px-4">
          <div className="w-full max-w-lg rounded-[2rem] border border-gray-200 bg-white p-6 shadow-2xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.22em] text-gray-400">
                  {t("approval_required", "Approval required")}
                </p>
                <h2 className="mt-2 text-xl font-semibold text-gray-950">
                  {t("approval_modal_title", "Review before continuing")}
                </h2>
              </div>
              <span className={`rounded-full border px-3 py-1 text-xs font-medium capitalize ${approvalRiskTone}`}>
                {approvalModal.riskLevel}
              </span>
            </div>

            <div className="mt-5 space-y-4">
              <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
                  {t("command", "Command")}
                </p>
                <p className="mt-2 text-sm leading-6 text-gray-900">{approvalModal.command}</p>
              </div>

              <div className="rounded-2xl border border-gray-200 bg-white p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
                  {t("approval_reason", "Approval reason")}
                </p>
                <p className="mt-2 text-sm leading-6 text-gray-700">
                  {approvalModal.reason ||
                    t(
                      "approval_reason_fallback",
                      "This action requires explicit permission before it can continue."
                    )}
                </p>
              </div>
            </div>

            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={handleRejectCurrentTask}
                disabled={approvalActionLoading !== null}
                className="rounded-2xl border border-gray-200 px-4 py-2.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:opacity-60"
              >
                {approvalActionLoading === "reject" ? t("rejecting", "Rejecting...") : t("reject")}
              </button>
              <button
                type="button"
                onClick={handleApproveCurrentTask}
                disabled={approvalActionLoading !== null}
                className="rounded-2xl bg-gray-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-gray-800 disabled:opacity-60"
              >
                {approvalActionLoading === "approve" ? t("approving", "Approving...") : t("approve")}
              </button>
            </div>
          </div>
        </div>
      )}
      <ConfirmDialog
        open={deleteDialog !== null}
        title={
          deleteDialog?.mode === "bulk"
            ? t("delete_selected_confirm_title", "선택한 실행 내역을 삭제할까요?")
            : t("delete_task_confirm_title", "이 실행 내역을 삭제할까요?")
        }
        description={
          deleteDialog?.mode === "bulk"
            ? t(
                "delete_selected_confirm_desc",
                "선택한 실행 내역, 결과, 승인 기록, 추적 로그를 함께 지웁니다."
              )
            : t(
                "delete_task_confirm_desc",
                "이 실행 내역의 결과, 승인 기록, 추적 로그를 함께 지웁니다."
              )
        }
        confirmLabel={t("delete")}
        cancelLabel={t("cancel", "취소")}
        tone="danger"
        busy={Boolean(deletingTaskId || bulkDeleting)}
        onCancel={() => setDeleteDialog(null)}
        onConfirm={() => {
          if (!deleteDialog) return;
          const current = deleteDialog;
          setDeleteDialog(null);
          if (current.mode === "single") {
            void handleDeleteTask(current.taskId);
            return;
          }
          void handleDeleteSelected(current.taskIds);
        }}
      />
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

        {backendStartupError && (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
            <p className="text-sm font-semibold text-amber-950">
              {t("backend_startup_failed_title", "백엔드 시작에 실패했습니다")}
            </p>
            <p className="mt-1 text-sm leading-6 text-amber-900">
              {t(
                "backend_startup_failed_desc",
                "앱 화면은 열렸지만 내부 백엔드를 붙이지 못했습니다. 아래 원인과 로그 파일 경로를 먼저 확인해주세요."
              )}
            </p>
            <p className="mt-3 whitespace-pre-wrap break-words rounded-xl border border-amber-200 bg-white/80 px-3 py-2 text-xs text-amber-900">
              {backendStartupError}
            </p>
            {backendStartupLogPath && (
              <p className="mt-2 break-all text-xs text-amber-800">
                {t("backend_startup_log_path", "로그 파일")}: {backendStartupLogPath}
              </p>
            )}
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
                {submitError && (
                  <div className="mt-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                    {submitError}
                  </div>
                )}
                <div className="mt-3 space-y-3">
                  {activeTasks.map((task) => (
                    <TaskCard
                      key={task.task_id}
                      task={task}
                      onDelete={(taskId) => setDeleteDialog({ mode: "single", taskId })}
                      deleting={deletingTaskId === task.task_id}
                      onRetry={handleRetryTask}
                      retrying={retryingTaskId === task.task_id}
                      onContinueWithAi={handleContinueWithAi}
                      continuingWithAi={continuingAiTaskId === task.task_id}
                      onClarificationAnswer={handleClarificationAnswer}
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
                {recentCompletedTasks.length > 0 && (
                  <div className="mt-5 space-y-3 border-t border-gray-100 pt-4">
                    <div>
                      <h3 className="text-sm font-semibold text-gray-950">
                        {t("latest_completed_title", "방금 끝난 작업")}
                      </h3>
                      <p className="mt-1 text-xs text-gray-500">
                        {t("latest_completed_desc", "실행 직후 작업이 사라져 보이지 않도록 최근 완료 작업을 잠깐 여기에도 남깁니다.")}
                      </p>
                    </div>
                    {recentCompletedTasks.map((task) => (
                      <TaskCard
                        key={`recent-${task.task_id}`}
                        task={task}
                        onDelete={(taskId) => setDeleteDialog({ mode: "single", taskId })}
                        deleting={deletingTaskId === task.task_id}
                        onRetry={handleRetryTask}
                        retrying={retryingTaskId === task.task_id}
                        onContinueWithAi={handleContinueWithAi}
                        continuingWithAi={continuingAiTaskId === task.task_id}
                        onClarificationAnswer={handleClarificationAnswer}
                      />
                    ))}
                  </div>
                )}
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
                        onClick={() =>
                          setDeleteDialog({
                            mode: "bulk",
                            taskIds: selectedVisibleCompletedTaskIds,
                          })
                        }
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
                        onDelete={(taskId) => setDeleteDialog({ mode: "single", taskId })}
                        deleting={deletingTaskId === task.task_id}
                        onRetry={handleRetryTask}
                        retrying={retryingTaskId === task.task_id}
                        onContinueWithAi={handleContinueWithAi}
                        continuingWithAi={continuingAiTaskId === task.task_id}
                        onClarificationAnswer={handleClarificationAnswer}
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
      </div>
    </main>
  );
}

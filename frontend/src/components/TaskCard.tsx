import { useState } from "react";
import { TaskResponse } from "@/lib/api";
import { useLanguage } from "@/components/LanguageProvider";
import { openExternalUrl } from "@/lib/external";

interface Props {
  task: TaskResponse;
  onDelete?: (taskId: string) => void;
  onRetry?: (taskId: string) => void;
  onContinueWithAi?: (taskId: string) => void;
  deleting?: boolean;
  retrying?: boolean;
  continuingWithAi?: boolean;
  selectable?: boolean;
  selected?: boolean;
  onToggleSelect?: (taskId: string) => void;
}

const statusColor: Record<TaskResponse["status"], string> = {
  pending: "bg-gray-100 text-gray-600",
  running: "bg-blue-100 text-blue-700",
  done: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  approval_required: "bg-yellow-100 text-yellow-700",
  cancelled: "bg-gray-200 text-gray-700",
};

export default function TaskCard({
  task,
  onDelete,
  onRetry,
  onContinueWithAi,
  deleting = false,
  retrying = false,
  continuingWithAi = false,
  selectable = false,
  selected = false,
  onToggleSelect,
}: Props) {
  const { t } = useLanguage();
  const [previewOpen, setPreviewOpen] = useState(false);
  const [aiPlanOpen, setAiPlanOpen] = useState(false);

  const resultItems = Array.isArray(task.result?.results)
    ? (
        task.result.results as Array<{
          success?: boolean;
          data?: {
            text?: string;
            url?: string;
            title?: string;
            action?: string;
            links?: { title?: string; url?: string }[];
            schedule_id?: string;
            cron?: string;
            command?: string;
            source_name?: string;
            source_url?: string;
            name?: string;
            draft_type?: string;
            recipient?: string;
            subject?: string;
            body?: string;
            ai_enhanced?: boolean;
          };
          error?: string;
        }>
      )
    : [];

  const statusLabel: Record<TaskResponse["status"], string> = {
    pending: t("pending"),
    running: t("running_status"),
    done: t("done"),
    failed: t("failed"),
    approval_required: t("approval_required"),
    cancelled: t("cancelled"),
  };

  const primaryResult =
    [...resultItems].reverse().find((result) => result.data?.action === "open_url")
    ?? resultItems[0];

  const crawlPreview = primaryResult?.data?.text?.slice(0, 280);
  const crawlUrl = primaryResult?.data?.url;
  const openActionUrl = primaryResult?.data?.action === "open_url" ? primaryResult?.data?.url : null;
  const openActionTitle = primaryResult?.data?.title || t("open_link");
  const purchaseAssist =
    primaryResult?.data?.action === "open_url" &&
    (primaryResult?.data as { purchase_intent?: boolean } | undefined)?.purchase_intent
      ? primaryResult?.data
      : null;
  const scheduleResult =
    primaryResult?.data?.action === "schedule_created" || primaryResult?.data?.action === "schedule_draft"
      ? primaryResult?.data
      : null;
  const draftResult =
    primaryResult?.data?.draft_type === "message" || primaryResult?.data?.draft_type === "email"
      ? primaryResult?.data
      : null;
  const searchLinks = primaryResult?.data?.links ?? [];
  const errorMessage = primaryResult?.error;
  const aiContinuation = (
    task.result as {
      original_summary?: string;
      ai_continuation?: { summary?: string; steps?: { tool?: string; description?: string }[] };
    } | null
  )?.ai_continuation;
  const originalSummary = (
    task.result as {
      original_summary?: string;
    } | null
  )?.original_summary;

  const finishedAt = task.completed_at || task.created_at;
  const formattedFinishedAt = finishedAt
    ? new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      }).format(new Date(finishedAt))
    : null;

  const actionButtons = (
    <div className="flex flex-wrap items-center gap-2">
      {onRetry && (task.status === "failed" || task.status === "cancelled") && (
        <button
          onClick={() => onRetry(task.task_id)}
          disabled={retrying}
          className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50"
        >
          {retrying ? t("running") : t("retry")}
        </button>
      )}
      {!draftResult && onContinueWithAi && task.status !== "pending" && task.status !== "running" && (
        <button
          onClick={() => onContinueWithAi(task.task_id)}
          disabled={continuingWithAi}
          className="rounded-full border border-violet-200 bg-violet-50 px-3 py-1.5 text-xs font-medium text-violet-800 hover:bg-violet-100 disabled:opacity-50"
        >
          {continuingWithAi ? t("running") : t("continue_with_ai")}
        </button>
      )}
      {onDelete && (
        <button
          onClick={() => {
            console.warn("[history] delete button clicked", {
              taskId: task.task_id,
              status: task.status,
              deleting,
            });
            onDelete(task.task_id);
          }}
          disabled={deleting}
          className="rounded-full border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50 disabled:opacity-50"
        >
          {deleting ? t("deleting") : t("delete")}
        </button>
      )}
    </div>
  );

  return (
    <div className="space-y-4 rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          {selectable && onToggleSelect && (
            <input
              type="checkbox"
              checked={selected}
              onChange={() => onToggleSelect(task.task_id)}
              className="h-4 w-4 rounded border-gray-300"
            />
          )}
          <span className="text-xs font-mono text-gray-400">{task.task_id.slice(0, 8)}...</span>
          {formattedFinishedAt && <span className="text-xs text-gray-400">{formattedFinishedAt}</span>}
        </div>
        <span className={`rounded-full px-2 py-1 text-xs font-medium ${statusColor[task.status]}`}>
          {statusLabel[task.status]}
        </span>
      </div>

      <div className="space-y-2">
        {task.command && <p className="text-sm font-medium text-gray-900 break-words">{task.command}</p>}
        {task.result?.summary && <p className="text-sm leading-6 text-gray-600">{task.result.summary}</p>}
        {originalSummary && originalSummary !== task.result?.summary && (
          <div className="rounded-2xl border border-gray-200 bg-gray-50 p-3">
            <p className="text-xs text-gray-500">{t("previous_result", "Previous result")}</p>
            <p className="mt-1 text-sm leading-6 text-gray-700">{originalSummary}</p>
          </div>
        )}
      </div>

      {crawlUrl && (
        <a
          href={crawlUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="block text-xs text-blue-600 hover:text-blue-700 break-all"
        >
          {crawlUrl}
        </a>
      )}

      {openActionUrl && (
        <button
          type="button"
          onClick={() => void openExternalUrl(openActionUrl)}
          className="inline-flex items-center rounded-full bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {openActionTitle}
        </button>
      )}

      {purchaseAssist && (
        <div className="space-y-1 rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <p className="text-xs font-medium text-amber-800">{t("purchase_helper_title")}</p>
          <p className="text-sm text-amber-900 break-words">
            {t("purchase_helper_desc")}
          </p>
        </div>
      )}

      {scheduleResult && (
        <div className="space-y-2 rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
          <p className="text-xs text-emerald-700">
            {scheduleResult.action === "schedule_created" ? t("schedule_created") : t("schedule_draft")}
          </p>
          {scheduleResult.name && (
            <p className="text-sm font-medium text-emerald-900 break-words">{scheduleResult.name}</p>
          )}
          {scheduleResult.cron && (
            <p className="text-xs font-mono text-emerald-700">{scheduleResult.cron}</p>
          )}
          {scheduleResult.source_name && scheduleResult.source_url && (
            <a
              href={scheduleResult.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="block text-xs text-emerald-700 hover:text-emerald-800 break-all"
            >
              {scheduleResult.source_name}
            </a>
          )}
          {scheduleResult.command && (
            <p className="text-xs text-emerald-800 break-words">{scheduleResult.command}</p>
          )}
        </div>
      )}

      {draftResult && (
        <div className="space-y-3 rounded-2xl border border-violet-200 bg-violet-50 p-4">
          <p className="text-xs text-violet-700">
            {draftResult.draft_type === "email" ? t("email_draft") : t("message_draft")}
          </p>
          {draftResult.recipient && (
            <p className="text-sm text-violet-900 break-words">
              <span className="font-medium">{t("recipient")}:</span> {draftResult.recipient}
            </p>
          )}
          {draftResult.subject && (
            <p className="text-sm text-violet-900 break-words">
              <span className="font-medium">{t("subject")}:</span> {draftResult.subject}
            </p>
          )}
          {draftResult.body && (
            <div className="rounded-2xl bg-white/80 p-3">
              <p className="mb-1 text-xs text-violet-700">{t("body")}</p>
              <p className="whitespace-pre-wrap break-words text-sm text-violet-950">{draftResult.body}</p>
            </div>
          )}
          {draftResult.ai_enhanced && (
            <p className="text-xs font-medium text-violet-700">
              {t("ai_continued")}
            </p>
          )}
          {onContinueWithAi && task.status !== "pending" && task.status !== "running" && (
            <button
              onClick={() => onContinueWithAi(task.task_id)}
              disabled={continuingWithAi}
              className="rounded-full bg-violet-700 px-4 py-2 text-sm font-medium text-white hover:bg-violet-800 disabled:opacity-50"
            >
              {continuingWithAi ? t("running") : t("continue_with_ai")}
            </button>
          )}
        </div>
      )}

      {aiContinuation && (
        <button
          type="button"
          onClick={() => setAiPlanOpen((prev) => !prev)}
          className="w-full rounded-2xl border border-violet-200 bg-violet-50 p-4 text-left"
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-medium text-violet-700">{t("ai_continuation_plan")}</p>
              {aiContinuation.summary && (
                <p className="mt-1 text-sm text-violet-950 break-words">{aiContinuation.summary}</p>
              )}
            </div>
            <span className="text-xs text-violet-600">{aiPlanOpen ? t("close") : t("open")}</span>
          </div>
          {aiPlanOpen && aiContinuation.steps && aiContinuation.steps.length > 0 && (
            <div className="mt-3 space-y-2">
              {aiContinuation.steps.map((step, index) => (
                <div key={`${step.tool || "step"}-${index}`} className="rounded-xl bg-white/80 p-3">
                  <p className="text-xs font-medium text-violet-700">
                    {step.tool || t("step")} {index + 1}
                  </p>
                  <p className="mt-1 text-sm text-violet-950 break-words">
                    {step.description || step.tool || t("ai_followup_step")}
                  </p>
                </div>
              ))}
            </div>
          )}
        </button>
      )}

      {resultItems.length > 1 && (
        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs font-medium text-gray-600">{t("execution_history", "Execution history")}</p>
            <span className="text-xs text-gray-500">{resultItems.length}</span>
          </div>
          <div className="mt-3 space-y-2">
            {resultItems.map((result, index) => {
              const data = result.data ?? {};
              const label =
                data.title
                || data.name
                || data.command
                || data.url
                || result.error
                || t("step");

              return (
                <div key={`result-${task.task_id}-${index}`} className="rounded-xl bg-white p-3">
                  <p className="text-xs font-medium text-gray-500">
                    {t("step")} {index + 1}
                  </p>
                  <p className="mt-1 text-sm text-gray-900 break-words">{label}</p>
                  {data.url && (
                    <button
                      type="button"
                      onClick={() => data.url && void openExternalUrl(data.url)}
                      className="mt-2 block text-xs text-blue-600 break-all"
                    >
                      {data.url}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {searchLinks.length > 0 && (
        <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4">
          <div className="mb-2 flex items-center justify-between gap-3">
            <p className="text-xs text-blue-700">{t("search_results")}</p>
            <span className="text-xs text-blue-500">{searchLinks.length}</span>
          </div>
          <div className="space-y-2">
            {searchLinks.map((link, index) => (
              <button
                type="button"
                key={`${link.url}-${index}`}
                onClick={() => link.url && void openExternalUrl(link.url)}
                className="block rounded-xl bg-white px-3 py-3 hover:bg-blue-100"
              >
                <p className="text-sm font-medium text-blue-900 break-words">
                  {link.title || link.url}
                </p>
                <p className="mt-1 text-xs text-blue-600 break-all">{link.url}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {crawlPreview && (
        <button
          type="button"
          onClick={() => setPreviewOpen((prev) => !prev)}
          className="w-full rounded-2xl border border-gray-200 bg-gray-50 p-4 text-left"
        >
          <div className="mb-1 flex items-center justify-between gap-3">
            <p className="text-xs text-gray-500">{t("preview")}</p>
            <span className="text-xs text-gray-500 hover:text-gray-700">
              {previewOpen ? t("close") : t("open")}
            </span>
          </div>
          {previewOpen && (
            <p className="whitespace-pre-wrap break-words text-sm text-gray-700">{crawlPreview}</p>
          )}
        </button>
      )}

      {!draftResult && actionButtons}

      {task.status === "failed" && errorMessage && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4">
          <p className="mb-1 text-xs text-red-500">{t("failure_reason")}</p>
          <p className="whitespace-pre-wrap break-words text-sm text-red-700">{errorMessage}</p>
        </div>
      )}
      {task.status === "failed" && !task.result?.summary && !errorMessage && (
        <p className="text-sm text-red-600">{t("execution_failed")}</p>
      )}
    </div>
  );
}

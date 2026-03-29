import { useState } from "react";
import { TaskResponse } from "@/lib/api";
import { useLanguage } from "@/components/LanguageProvider";

interface Props {
  task: TaskResponse;
  onDelete?: (taskId: string) => void;
  onRetry?: (taskId: string) => void;
  deleting?: boolean;
  retrying?: boolean;
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
  deleting = false,
  retrying = false,
  selectable = false,
  selected = false,
  onToggleSelect,
}: Props) {
  const { t } = useLanguage();
  const [previewOpen, setPreviewOpen] = useState(false);
  const statusLabel: Record<TaskResponse["status"], string> = {
    pending: t("pending"),
    running: t("running_status"),
    done: t("done"),
    failed: t("failed"),
    approval_required: t("approval_required"),
    cancelled: t("cancelled"),
  };
  const firstResult = task.result?.results?.[0] as
    | {
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
        };
        error?: string;
      }
    | undefined;
  const crawlPreview = firstResult?.data?.text?.slice(0, 280);
  const crawlUrl = firstResult?.data?.url;
  const openActionUrl = firstResult?.data?.action === "open_url" ? firstResult?.data?.url : null;
  const openActionTitle = firstResult?.data?.title || t("open_link");
  const purchaseAssist =
    firstResult?.data?.action === "open_url" && (firstResult?.data as { purchase_intent?: boolean } | undefined)?.purchase_intent
      ? firstResult?.data
      : null;
  const scheduleResult =
    firstResult?.data?.action === "schedule_created" || firstResult?.data?.action === "schedule_draft"
      ? firstResult?.data
      : null;
  const draftResult =
    firstResult?.data?.draft_type === "message" || firstResult?.data?.draft_type === "email"
      ? firstResult?.data
      : null;
  const searchLinks = firstResult?.data?.links ?? [];
  const errorMessage = firstResult?.error;

  const finishedAt = task.completed_at || task.created_at;
  const formattedFinishedAt = finishedAt
    ? new Intl.DateTimeFormat(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      }).format(new Date(finishedAt))
    : null;

  return (
    <div className="border border-gray-200 rounded-lg p-4 space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {selectable && onToggleSelect && (
            <input
              type="checkbox"
              checked={selected}
              onChange={() => onToggleSelect(task.task_id)}
              className="h-4 w-4 rounded border-gray-300"
            />
          )}
          <span className="text-xs text-gray-400 font-mono">{task.task_id.slice(0, 8)}...</span>
        </div>
        <div className="flex items-center gap-2">
          {formattedFinishedAt && (
            <span className="text-xs text-gray-400">{formattedFinishedAt}</span>
          )}
          <span className={`text-xs px-2 py-1 rounded-full font-medium ${statusColor[task.status]}`}>
            {statusLabel[task.status]}
          </span>
          {onRetry && (task.status === "failed" || task.status === "cancelled") && (
            <button
              onClick={() => onRetry(task.task_id)}
              disabled={retrying}
              className="text-xs text-blue-500 hover:text-blue-700 disabled:opacity-50"
            >
              {retrying ? t("running") : t("retry", "재실행")}
            </button>
          )}
          {onDelete && (
            <button
              onClick={() => onDelete(task.task_id)}
              disabled={deleting}
              className="text-xs text-gray-400 hover:text-red-600 disabled:opacity-50"
            >
              {deleting ? t("deleting") : t("delete")}
            </button>
          )}
        </div>
      </div>
      {task.command && (
        <p className="text-sm text-gray-500 break-words">{task.command}</p>
      )}
      {task.result?.summary && (
        <p className="text-sm text-gray-800">{task.result.summary}</p>
      )}
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
        <a
          href={openActionUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          {openActionTitle}
        </a>
      )}
      {purchaseAssist && (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 space-y-1">
          <p className="text-xs font-medium text-amber-800">구매 진행 안내</p>
          <p className="text-sm text-amber-900 break-words">
            최저가나 구매 가능한 상품 페이지까지 연결했습니다. 실제 결제 전에는 상품 옵션, 배송비, 로그인 상태를 한 번 더 확인하세요.
          </p>
        </div>
      )}
      {scheduleResult && (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 space-y-2">
          <p className="text-xs text-emerald-700">
            {scheduleResult.action === "schedule_created" ? t("schedule_created") : t("schedule_draft")}
          </p>
          {scheduleResult.name && (
            <p className="text-sm font-medium text-emerald-900 break-words">{scheduleResult.name}</p>
          )}
          {scheduleResult.cron && (
            <p className="text-xs text-emerald-700 font-mono">{scheduleResult.cron}</p>
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
        <div className="rounded-md border border-violet-200 bg-violet-50 p-3 space-y-2">
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
            <div className="rounded-md bg-white/80 p-3">
              <p className="mb-1 text-xs text-violet-700">{t("body")}</p>
              <p className="text-sm text-violet-950 whitespace-pre-wrap break-words">{draftResult.body}</p>
            </div>
          )}
        </div>
      )}
      {searchLinks.length > 0 && (
        <div className="rounded-md border border-blue-100 bg-blue-50 p-3">
          <div className="mb-2 flex items-center justify-between gap-3">
            <p className="text-xs text-blue-700">{t("search_results")}</p>
            <span className="text-xs text-blue-500">{searchLinks.length}</span>
          </div>
          <div className="space-y-2">
            {searchLinks.map((link, index) => (
              <a
                key={`${link.url}-${index}`}
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block rounded-md bg-white px-3 py-2 hover:bg-blue-100"
              >
                <p className="text-sm font-medium text-blue-900 break-words">
                  {link.title || link.url}
                </p>
                <p className="mt-1 text-xs text-blue-600 break-all">{link.url}</p>
              </a>
            ))}
          </div>
        </div>
      )}
      {crawlPreview && (
        <button
          type="button"
          onClick={() => setPreviewOpen((prev) => !prev)}
          className="w-full rounded-md border border-gray-200 bg-gray-50 p-3 text-left"
        >
          <div className="mb-1 flex items-center justify-between gap-3">
            <p className="text-xs text-gray-500">{t("preview")}</p>
            <span className="text-xs text-gray-500 hover:text-gray-700">
              {previewOpen ? t("close") : t("open")}
            </span>
          </div>
          {previewOpen && (
            <p className="text-sm text-gray-700 whitespace-pre-wrap break-words">{crawlPreview}</p>
          )}
        </button>
      )}
      {task.status === "failed" && errorMessage && (
        <div className="rounded-md bg-red-50 border border-red-200 p-3">
          <p className="text-xs text-red-500 mb-1">{t("failure_reason")}</p>
          <p className="text-sm text-red-700 whitespace-pre-wrap break-words">{errorMessage}</p>
        </div>
      )}
      {task.status === "failed" && !task.result?.summary && !errorMessage && (
        <p className="text-sm text-red-600">{t("execution_failed")}</p>
      )}
    </div>
  );
}

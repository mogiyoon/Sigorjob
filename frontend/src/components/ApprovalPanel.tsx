"use client";

import { ApprovalItem, approveTask, rejectTask } from "@/lib/api";
import { useLanguage } from "@/components/LanguageProvider";

interface Props {
  approvals: ApprovalItem[];
  onResolved: () => void;
}

export default function ApprovalPanel({ approvals, onResolved }: Props) {
  const { t } = useLanguage();
  if (approvals.length === 0) return null;

  return (
    <section className="bg-white border border-yellow-200 rounded-xl p-4 space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-gray-900">{t("approvals_title")}</h2>
        <p className="text-xs text-gray-500">{t("approvals_desc")}</p>
      </div>
      <div className="space-y-3">
        {approvals.map((approval) => (
          <div key={approval.task_id} className="border border-gray-200 rounded-lg p-3 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <code className="text-xs text-gray-400">{approval.task_id.slice(0, 8)}...</code>
              <span className="text-xs px-2 py-1 rounded-full bg-yellow-100 text-yellow-800">
                {approval.risk_level === "high" ? "주의" : approval.risk_level === "medium" ? "확인 필요" : approval.risk_level}
              </span>
            </div>
            <p className="text-sm text-gray-800">{approval.command}</p>
            {approval.reason && <p className="text-xs text-gray-500">{approval.reason}</p>}
            <div className="flex gap-2">
              <button
                onClick={async () => {
                  await approveTask(approval.task_id);
                  onResolved();
                }}
                className="px-3 py-1.5 rounded-lg bg-green-600 text-white text-sm hover:bg-green-700"
              >
                {t("approve")}
              </button>
              <button
                onClick={async () => {
                  await rejectTask(approval.task_id);
                  onResolved();
                }}
                className="px-3 py-1.5 rounded-lg bg-gray-200 text-gray-700 text-sm hover:bg-gray-300"
              >
                {t("reject")}
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

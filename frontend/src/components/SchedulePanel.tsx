"use client";

import { FormEvent, useState } from "react";
import { createSchedule, deleteSchedule, ScheduleItem } from "@/lib/api";
import { useLanguage } from "@/components/LanguageProvider";

interface Props {
  schedules: ScheduleItem[];
  onChanged: () => void;
}

export default function SchedulePanel({ schedules, onChanged }: Props) {
  const { t } = useLanguage();
  const [name, setName] = useState("");
  const [command, setCommand] = useState("");
  const [cron, setCron] = useState("0 9 * * *");
  const [saving, setSaving] = useState(false);

  const sortedSchedules = [...schedules].sort((a, b) => {
    const left = a.next_run_at ? new Date(a.next_run_at).getTime() : Number.MAX_SAFE_INTEGER;
    const right = b.next_run_at ? new Date(b.next_run_at).getTime() : Number.MAX_SAFE_INTEGER;
    return left - right;
  });

  const quickCrons = [
    { label: t("weekday_morning", "평일 오전 9시"), value: "0 9 * * 1-5" },
    { label: t("daily_morning", "매일 오전 8시"), value: "0 8 * * *" },
    { label: t("daily_evening", "매일 저녁 6시"), value: "0 18 * * *" },
  ];

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || !command.trim() || !cron.trim() || saving) return;
    setSaving(true);
    try {
      await createSchedule({
        name: name.trim(),
        command: command.trim(),
        cron: cron.trim(),
      });
      setName("");
      setCommand("");
      setCron("0 9 * * *");
      onChanged();
    } finally {
      setSaving(false);
    }
  }

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

  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-4 md:p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-gray-900">{t("schedules_title", "루틴")}</h2>
          <p className="text-xs text-gray-500">{t("schedules_desc", "반복해서 돌릴 작업을 등록하고 관리합니다.")}</p>
        </div>
        <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
          {schedules.length}{t("count_suffix", "개")}
        </span>
      </div>

      <form onSubmit={handleSubmit} className="grid gap-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("schedule_name_placeholder", "루틴 이름")}
          className="rounded-xl border border-gray-300 px-3 py-2 text-sm"
        />
        <input
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          placeholder={t("command_to_run", "실행할 내용")}
          className="rounded-xl border border-gray-300 px-3 py-2 text-sm"
        />
        <input
          value={cron}
          onChange={(e) => setCron(e.target.value)}
          placeholder={t("repeat_time_placeholder", "반복 시간")}
          className="rounded-xl border border-gray-300 px-3 py-2 text-sm font-mono"
        />
        <div className="flex flex-wrap gap-2 pt-1">
          {quickCrons.map((preset) => (
            <button
              key={preset.value}
              type="button"
              onClick={() => setCron(preset.value)}
              className="rounded-full border border-gray-200 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-50"
            >
              {preset.label}
            </button>
          ))}
        </div>
        <button
          type="submit"
          disabled={saving}
          className="justify-self-start rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {saving ? t("adding_schedule", "추가 중...") : t("add_schedule", "루틴 추가")}
        </button>
      </form>

      <div className="space-y-3">
        {sortedSchedules.map((schedule) => (
          <div key={schedule.schedule_id} className="rounded-xl border border-gray-200 p-4 space-y-3">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-gray-900">{schedule.name}</p>
                <p className="text-xs font-mono text-gray-500">{schedule.cron}</p>
              </div>
              <button
                onClick={async () => {
                  await deleteSchedule(schedule.schedule_id);
                  onChanged();
                }}
                className="rounded-lg bg-gray-100 px-2.5 py-1 text-xs text-gray-700 hover:bg-gray-200"
              >
                {t("delete")}
              </button>
            </div>
            <p className="text-sm text-gray-700">{schedule.command}</p>
            <div className="grid gap-2 text-xs text-gray-500 md:grid-cols-2">
              <p>{t("next_run", "다음 실행")}: {formatDateTime(schedule.next_run_at)}</p>
              <p>{t("last_run", "최근 실행")}: {formatDateTime(schedule.last_run_at)}</p>
            </div>
          </div>
        ))}

        {sortedSchedules.length === 0 && (
          <div className="rounded-xl border border-dashed border-gray-200 bg-gray-50 p-5 text-sm text-gray-500">
            {t("routine_empty_desc", "아직 등록된 루틴이 없습니다.")}
          </div>
        )}
      </div>
    </section>
  );
}

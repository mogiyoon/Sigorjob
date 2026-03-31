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

  console.warn("[routines] SchedulePanel render", {
    schedules: schedules.length,
    sortedSchedules: sortedSchedules.length,
    scheduleIds: sortedSchedules.map((schedule) => schedule.schedule_id),
  });

  const quickCrons = [
    { label: t("weekday_morning"), value: "0 9 * * 1-5" },
    { label: t("daily_morning"), value: "0 8 * * *" },
    { label: t("daily_evening"), value: "0 18 * * *" },
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

  return (
    <section className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-gray-400">
            {t("routines")}
          </p>
          <h2 className="mt-1 text-base font-semibold text-gray-950">
            {t("schedules_title")}
          </h2>
          <p className="mt-1 text-sm text-gray-500">
            {t("schedules_desc")}
          </p>
        </div>
        <span className="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-medium text-gray-700">
          {schedules.length}{t("count_suffix")}
        </span>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[0.95fr_1.05fr]">
        <form onSubmit={handleSubmit} className="space-y-3 rounded-2xl border border-gray-200 bg-gray-50 p-4">
          <div className="space-y-1">
            <p className="text-sm font-medium text-gray-900">{t("add_schedule")}</p>
            <p className="text-xs text-gray-500">
              {t("schedule_form_desc")}
            </p>
          </div>

          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("schedule_name_placeholder")}
            className="w-full rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm"
          />
          <textarea
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            placeholder={t("command_to_run")}
            rows={3}
            className="w-full rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm"
          />
          <input
            value={cron}
            onChange={(e) => setCron(e.target.value)}
            placeholder={t("repeat_time_placeholder")}
            className="w-full rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm font-mono"
          />
          <div className="flex flex-wrap gap-2">
            {quickCrons.map((preset) => (
              <button
                key={preset.value}
                type="button"
                onClick={() => setCron(preset.value)}
                className="rounded-full border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100"
              >
                {preset.label}
              </button>
            ))}
          </div>
          <button
            type="submit"
            disabled={saving}
            className="rounded-full bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? t("adding_schedule") : t("add_schedule")}
          </button>
        </form>

        <div className="space-y-3">
          {sortedSchedules.map((schedule) => (
            <div key={schedule.schedule_id} className="rounded-2xl border border-gray-200 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-gray-900">{schedule.name}</p>
                  <p className="mt-1 text-xs font-mono text-gray-500">{schedule.cron}</p>
                </div>
                <button
                  onClick={async () => {
                    await deleteSchedule(schedule.schedule_id);
                    onChanged();
                  }}
                  className="rounded-full border border-gray-200 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50"
                >
                  {t("delete")}
                </button>
              </div>
              <p className="mt-3 text-sm leading-6 text-gray-600">{schedule.command}</p>
              <div className="mt-4 grid gap-2 rounded-2xl bg-gray-50 p-3 text-xs text-gray-500 sm:grid-cols-2">
                <p>{t("next_run")}: {formatDateTime(schedule.next_run_at)}</p>
                <p>{t("last_run")}: {formatDateTime(schedule.last_run_at)}</p>
              </div>
            </div>
          ))}

          {sortedSchedules.length === 0 && (
            <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 p-5 text-sm text-gray-500">
              {t("routine_empty_desc")}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

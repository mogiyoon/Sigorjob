"use client";

import Link from "next/link";
import { useLanguage } from "@/components/LanguageProvider";

export default function SetupToolsPage() {
  const { t } = useLanguage();

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
              {t("setup_tools_title", "도구 설정")}
            </h1>
            <p className="text-sm text-gray-500">
              {t("setup_tools_placeholder", "로컬 도구 설정 항목을 여기에 표시할 예정입니다.")}
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}

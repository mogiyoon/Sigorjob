"use client";

import { useState } from "react";
import { useLanguage } from "@/components/LanguageProvider";

interface Props {
  onSubmit: (text: string) => Promise<boolean | void>;
  loading: boolean;
}

export default function CommandInput({ onSubmit, loading }: Props) {
  const [text, setText] = useState("");
  const { t } = useLanguage();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || loading) return;
    const submitted = await onSubmit(text.trim());
    if (submitted !== false) {
      setText("");
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={t("input_placeholder")}
        disabled={loading}
        className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={loading || !text.trim()}
        className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? t("running") : t("run")}
      </button>
    </form>
  );
}

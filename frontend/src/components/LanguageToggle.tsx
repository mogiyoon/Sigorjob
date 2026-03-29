"use client";

import { useLanguage } from "@/components/LanguageProvider";

export default function LanguageToggle() {
  const { locale, setLocale } = useLanguage();

  return (
    <div className="inline-flex rounded-full border border-gray-200 bg-white p-1 shadow-sm">
      {(["ko", "en"] as const).map((item) => (
        <button
          key={item}
          onClick={() => setLocale(item)}
          className={`rounded-full px-3 py-1 text-xs font-medium ${
            locale === item
              ? "bg-gray-900 text-white"
              : "text-gray-600 hover:bg-gray-100"
          }`}
        >
          {item.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[Sigorjob Error Boundary]", error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-950">오류가 발생했습니다</h2>
        <p className="mt-2 text-sm text-gray-600">{error.message}</p>
        <pre className="mt-3 max-h-40 overflow-auto rounded-lg bg-gray-100 p-3 text-xs text-gray-700">
          {error.stack}
        </pre>
        <button
          onClick={reset}
          className="mt-4 rounded-2xl bg-gray-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-800"
        >
          다시 시도
        </button>
      </div>
    </div>
  );
}

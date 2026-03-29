"use client";

import { useEffect } from "react";
import { initTokenFromUrl } from "@/lib/api";

/** URL의 _token 파라미터를 localStorage에 저장하고 URL에서 제거 */
export default function TokenInitializer() {
  useEffect(() => {
    initTokenFromUrl();
  }, []);
  return null;
}

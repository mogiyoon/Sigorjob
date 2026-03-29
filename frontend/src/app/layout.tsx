import type { Metadata } from "next";
import "./globals.css";
import TokenInitializer from "@/components/TokenInitializer";
import { LanguageProvider } from "@/components/LanguageProvider";

export const metadata: Metadata = {
  title: "Sigorjob",
  description: "Local automation platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <LanguageProvider>
          <TokenInitializer />
          {children}
        </LanguageProvider>
      </body>
    </html>
  );
}

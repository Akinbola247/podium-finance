import "./globals.css";
import React, { Suspense } from "react";
import { StreamProvider } from "../context/stream-context";
import { AppHeader } from "../components/layout/app-header";

export const metadata = {
  title: "Podium Finance",
  description: "Whale intelligence and risk-aware execution planning for Injective",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <StreamProvider>
          <AppHeader />
          <Suspense fallback={<main className="p-6 font-mono text-sm text-text-muted">Loading…</main>}>
            {children}
          </Suspense>
          <footer className="border-t border-border px-4 py-3 text-center font-mono text-[10px] text-text-muted">
            Educational analytics only — not financial advice. On-chain data from Injective mainnet.
          </footer>
        </StreamProvider>
      </body>
    </html>
  );
}

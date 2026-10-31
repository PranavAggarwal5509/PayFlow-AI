import "@/styles/globals.css";

import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Toaster } from "sonner";

import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";

export const metadata: Metadata = {
  title: "PayFlow AI — Intelligent Invoice Processing & Decision System",
  description: "Enterprise AI-assisted invoice processing with deterministic financial verification and explainable decisions.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased bg-slate-50 text-foreground selection:bg-blue-100 selection:text-blue-900">
        <div className="flex min-h-screen">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <Topbar />
            <main className="mx-auto w-full max-w-[1440px] flex-1 p-6 lg:p-8">{children}</main>
          </div>
        </div>
        <Toaster position="top-right" richColors closeButton />
      </body>
    </html>
  );
}


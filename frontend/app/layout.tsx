import "@/styles/globals.css";

import type { Metadata } from "next";
import { Inter } from "next/font/google";
import type { ReactNode } from "react";
import { Toaster } from "sonner";

import { AppShell } from "@/components/auth/app-shell";
import { AuthProvider } from "@/components/auth/auth-provider";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: "PayFlow AI — Intelligent Invoice Processing & Decision System",
  description: "Enterprise AI-assisted invoice processing with deterministic financial verification and explainable decisions.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen overflow-x-clip bg-canvas font-sans text-foreground antialiased selection:bg-indigo-100 selection:text-indigo-900">
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
        <Toaster position="top-right" richColors closeButton />
      </body>
    </html>
  );
}

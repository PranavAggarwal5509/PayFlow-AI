"use client";

import { Lock } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { Logo, TopNav } from "@/components/layout/top-nav";
import { permissionForPath, ROLE_STYLE } from "@/lib/permissions";

/** Chrome around every page: nav + hero band when signed in; a bare canvas for /login. */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, ready, can } = useAuth();

  if (pathname.startsWith("/login")) return <>{children}</>;

  if (!ready || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-navy-950">
        <div className="flex flex-col items-center gap-4">
          <Logo className="h-12 w-12 animate-pulse rounded-2xl" />
          <p className="text-[13px] text-slate-400">Securing your session…</p>
        </div>
      </div>
    );
  }

  const needed = permissionForPath(pathname);
  const allowed = !needed || can(needed);

  return (
    <>
      <TopNav />
      <div className="relative">
        <div aria-hidden className="hero-band pointer-events-none absolute inset-x-0 top-0 h-[300px]" />
        <main className="relative mx-auto w-full max-w-[1480px] px-4 pb-16 pt-8 sm:px-6 lg:px-8 lg:pt-10">
          {allowed ? children : <NoAccess role={user.role_label} roleKey={user.role} />}
        </main>
      </div>
    </>
  );
}

function NoAccess({ role, roleKey }: { role: string; roleKey: string }) {
  const style = ROLE_STYLE[roleKey] ?? ROLE_STYLE.AUDITOR;
  return (
    <div className="mx-auto mt-16 max-w-lg animate-fade-up rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-lift">
      <span className={`mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br ${style.gradient} text-white shadow-lg`}>
        <Lock className="h-6 w-6" />
      </span>
      <h1 className="mt-5 text-[20px] font-semibold text-slate-900">This area is not part of your role</h1>
      <p className="mt-2 text-[14px] text-slate-500">
        You are signed in as <span className="font-semibold text-slate-800">{role}</span>. Ask an administrator for
        access, or switch to an account that has it.
      </p>
      <div className="mt-6 flex justify-center gap-2">
        <Link href="/dashboard" className="rounded-lg bg-navy-900 px-4 py-2 text-[13px] font-semibold text-white hover:bg-navy-800">
          Back to overview
        </Link>
        <Link href="/login?switch=1" className="rounded-lg border border-slate-200 px-4 py-2 text-[13px] font-semibold text-slate-700 hover:bg-slate-50">
          Switch account
        </Link>
      </div>
    </div>
  );
}

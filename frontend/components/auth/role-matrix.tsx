"use client";

import { Check, Minus, ShieldCheck } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAsync } from "@/hooks/use-async";
import { PERMISSION_LABELS, ROLE_STYLE } from "@/lib/permissions";
import { cn } from "@/lib/utils";
import { authService } from "@/services";

/** Role × permission matrix, read from the same map the API enforces. */
export function RoleMatrix() {
  const { user } = useAuth();
  const data = useAsync(() => authService.roles(), []);
  const roles = data.data?.roles ?? [];
  const permissions = data.data?.permissions ?? [];

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <div>
          <p className="eyebrow">Access control</p>
          <h3 className="mt-1 text-[15px] font-semibold text-slate-900">Roles &amp; permissions</h3>
          <p className="mt-0.5 text-[12.5px] text-slate-500">
            Enforced by the API on every request — the interface simply hides what a role cannot use.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[11.5px] font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200">
          <ShieldCheck className="h-3.5 w-3.5" /> Server-enforced
        </span>
      </div>
      {data.loading && !data.data ? (
        <div className="space-y-2 p-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-[13px]">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50/70">
                <th className="px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Permission</th>
                {roles.map((role) => {
                  const style = ROLE_STYLE[role.role] ?? ROLE_STYLE.AUDITOR;
                  const mine = user?.role === role.role;
                  return (
                    <th key={role.role} className={cn("px-3 py-3 text-center", mine && "bg-indigo-50/60")}>
                      <span className="inline-flex flex-col items-center gap-1">
                        <span className={cn("h-2 w-8 rounded-full bg-gradient-to-r", style.gradient)} />
                        <span className="text-[12px] font-semibold text-slate-800">{role.label}</span>
                        {mine && <span className="text-[10px] font-semibold uppercase tracking-wider text-indigo-600">You</span>}
                      </span>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {permissions.map((permission, i) => (
                <tr key={permission} className="reveal hover:bg-slate-50/60" style={{ ["--d" as string]: `${i * 40}ms` }}>
                  <td className="px-5 py-2.5">
                    <span className="font-medium text-slate-800">{PERMISSION_LABELS[permission] ?? permission}</span>
                    <span className="ml-2 font-mono text-[11px] text-slate-400">{permission}</span>
                  </td>
                  {roles.map((role) => {
                    const has = role.permissions.includes(permission);
                    const mine = user?.role === role.role;
                    return (
                      <td key={role.role} className={cn("px-3 py-2.5 text-center", mine && "bg-indigo-50/40")}>
                        {has ? (
                          <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-emerald-50 text-emerald-600 ring-1 ring-inset ring-emerald-200">
                            <Check className="h-3.5 w-3.5" strokeWidth={3} />
                            <span className="sr-only">Allowed</span>
                          </span>
                        ) : (
                          <span className="inline-flex h-6 w-6 items-center justify-center text-slate-300">
                            <Minus className="h-3.5 w-3.5" />
                            <span className="sr-only">Not allowed</span>
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="grid gap-3 border-t border-slate-100 p-5 sm:grid-cols-2 xl:grid-cols-5">
        {roles.map((role) => {
          const style = ROLE_STYLE[role.role] ?? ROLE_STYLE.AUDITOR;
          return (
            <div key={role.role} className="rounded-xl border border-slate-100 p-3">
              <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold", style.soft, style.text)}>
                <span className={cn("h-1.5 w-1.5 rounded-full", style.dot)} /> {role.label}
              </span>
              <p className="mt-2 text-[12.5px] leading-relaxed text-slate-600">{role.summary}</p>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

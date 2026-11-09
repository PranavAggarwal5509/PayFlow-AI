"use client";

import { ShieldAlert, ShieldCheck, Wallet } from "lucide-react";
import Link from "next/link";

import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useMounted } from "@/hooks/use-motion";
import { formatMoney } from "@/lib/format";
import { ISSUE_LABELS } from "@/lib/status";

const CONTROL_FAMILY: Record<string, string> = {
  VENDOR_BANK: "Fraud",
  APPROVAL_LIMIT: "Authority",
  DUP_FILE: "Duplicate",
  DUP_BUSINESS: "Duplicate",
  DUP_POTENTIAL: "Duplicate",
  PO_EXISTS: "Procurement",
  PO_BALANCE: "Procurement",
  PO_CURRENCY: "Procurement",
  PO_LINE_ITEMS: "Procurement",
  PO_VENDOR: "Procurement",
  PO_STATUS: "Procurement",
  VENDOR_MATCH: "Vendor",
  VENDOR_STATUS: "Vendor",
  VENDOR_GSTIN: "Tax",
  TAX_RATES: "Tax",
};

export function ExceptionsByControl({
  data,
  loading,
}: {
  data: { code: string; count: number }[] | undefined;
  loading: boolean;
}) {
  const max = Math.max(1, ...(data ?? []).map((d) => d.count));
  const mounted = useMounted();
  return (
    <Card className="flex h-full flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="eyebrow">Control effectiveness</p>
          <h3 className="mt-1 text-[15px] font-semibold">Exceptions caught, by control</h3>
          <p className="mt-0.5 text-[12.5px] text-slate-500">Which rules stopped or flagged live invoices.</p>
        </div>
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-50 text-amber-600 ring-1 ring-inset ring-amber-100">
          <ShieldAlert className="h-[18px] w-[18px]" />
        </span>
      </div>
      <div className="mt-4 flex-1">
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-6 w-full" />
            ))}
          </div>
        ) : !data || data.length === 0 ? (
          <div className="flex h-full min-h-[160px] flex-col items-center justify-center rounded-lg border border-dashed border-slate-200 text-center">
            <ShieldCheck className="h-6 w-6 text-emerald-500" />
            <p className="mt-2 text-[13px] font-medium text-slate-700">No exceptions yet</p>
            <p className="text-[12px] text-slate-500">Run an edge-case scenario to see controls fire.</p>
          </div>
        ) : (
          <ul className="space-y-2.5">
            {data.slice(0, 8).map((row, i) => (
              <li key={row.code}>
                <Link href="/review" className="group block">
                  <div className="flex items-center justify-between gap-3 text-[12.5px]">
                    <span className="flex min-w-0 items-center gap-2">
                      <span className="truncate font-medium text-slate-800 group-hover:text-indigo-700">
                        {ISSUE_LABELS[row.code] ?? row.code}
                      </span>
                      {CONTROL_FAMILY[row.code] && (
                        <span className="shrink-0 rounded bg-slate-100 px-1.5 py-px text-[10.5px] font-medium text-slate-500">
                          {CONTROL_FAMILY[row.code]}
                        </span>
                      )}
                    </span>
                    <span className="tabular font-semibold text-slate-900">{row.count}</span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-amber-400 to-orange-500"
                      style={{
                        width: mounted ? `${(row.count / max) * 100}%` : "0%",
                        transition: `width 0.9s cubic-bezier(0.22, 1, 0.36, 1) ${0.3 + i * 0.06}s`,
                      }}
                    />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

type Buckets = { held: Record<string, string | number>; blocked: Record<string, string | number>; approved: Record<string, string | number> };

export function ValueAtRisk({
  data,
  touchless,
  loading,
}: {
  data: Buckets | undefined;
  touchless: number | null | undefined;
  loading: boolean;
}) {
  const currencies = Array.from(
    new Set([...Object.keys(data?.approved ?? {}), ...Object.keys(data?.held ?? {}), ...Object.keys(data?.blocked ?? {})]),
  ).sort((a, b) => (a === "INR" ? -1 : b === "INR" ? 1 : a.localeCompare(b)));
  const rows = [
    { key: "approved" as const, label: "Cleared for payment", dot: "bg-emerald-500" },
    { key: "held" as const, label: "Held for review", dot: "bg-amber-500" },
    { key: "blocked" as const, label: "Blocked (rejected)", dot: "bg-rose-500" },
  ];
  return (
    <Card className="flex h-full flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="eyebrow">Spend control</p>
          <h3 className="mt-1 text-[15px] font-semibold">Invoice value by outcome</h3>
          <p className="mt-0.5 text-[12.5px] text-slate-500">Money that moved, waited, or was stopped.</p>
        </div>
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 ring-1 ring-inset ring-indigo-100">
          <Wallet className="h-[18px] w-[18px]" />
        </span>
      </div>
      <div className="mt-4 rounded-lg bg-navy-900 px-4 py-3.5 text-white">
        <p className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Touchless rate</p>
        <div className="mt-1 flex items-end gap-2">
          <span className="tabular text-3xl font-semibold">{loading ? "—" : touchless != null ? `${touchless}%` : "—"}</span>
          <span className="pb-1 text-[12px] text-slate-400">approved with zero human touches</span>
        </div>
      </div>
      <div className="mt-4 flex-1 space-y-3">
        {loading ? (
          <Skeleton className="h-24 w-full" />
        ) : currencies.length === 0 ? (
          <p className="text-[12.5px] text-slate-500">No decided invoices yet.</p>
        ) : (
          rows.map((row) => (
            <div key={row.key} className="flex items-start justify-between gap-3 text-[13px]">
              <span className="flex items-center gap-2 text-slate-600">
                <span className={`h-2 w-2 rounded-full ${row.dot}`} />
                {row.label}
              </span>
              <span className="text-right">
                {currencies.filter((cur) => Number(data?.[row.key][cur] ?? 0) > 0).length === 0 ? (
                  <span className="text-slate-400">—</span>
                ) : (
                  currencies
                    .filter((cur) => Number(data?.[row.key][cur] ?? 0) > 0)
                    .map((cur) => (
                      <span key={cur} className="block tabular font-semibold text-slate-900">
                        {formatMoney(data?.[row.key][cur] ?? 0, cur)}
                      </span>
                    ))
                )}
              </span>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

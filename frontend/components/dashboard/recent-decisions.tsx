"use client";

import { ChevronRight, Inbox } from "lucide-react";
import Link from "next/link";

import { VendorCell } from "@/components/invoices/invoice-columns";
import { InvoiceStateBadge } from "@/components/invoices/status-badges";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime, formatMoney } from "@/lib/format";
import type { InvoiceListItem } from "@/types/api";

/** Compact decision feed for the overview — one line per invoice, no horizontal scroll. */
export function RecentDecisions({ items, loading }: { items: InvoiceListItem[]; loading: boolean }) {
  if (loading && items.length === 0) {
    return (
      <div className="space-y-2 p-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <div className="flex min-h-[220px] flex-col items-center justify-center text-center">
        <Inbox className="h-7 w-7 text-slate-300" />
        <p className="mt-2 text-[13px] font-medium text-slate-600">No invoices yet</p>
        <Link href="/upload" className="mt-1 text-[13px] font-semibold text-indigo-600">
          Process your first invoice →
        </Link>
      </div>
    );
  }
  return (
    <ul className="divide-y divide-slate-100">
      {items.map((inv, i) => {
        const href =
          inv.processing_status === "PROCESSING" && inv.latest_run_id ? `/processing/${inv.latest_run_id}` : `/invoices/${inv.id}`;
        return (
          <li key={inv.id} className="reveal" style={{ ["--d" as string]: `${700 + i * 50}ms` }}>
            <Link href={href} className="group flex items-center gap-4 px-5 py-3 transition-colors hover:bg-indigo-50/40">
              <div className="min-w-0 flex-1">
                <VendorCell name={inv.vendor_name} />
              </div>
              <div className="hidden min-w-0 flex-1 sm:block">
                <p className="truncate text-[13px] font-semibold text-slate-900">{inv.invoice_number ?? "No number"}</p>
                <p className="truncate text-[11.5px] text-slate-400">{formatDateTime(inv.uploaded_at)}</p>
              </div>
              <span className="tabular w-28 shrink-0 text-right text-[13.5px] font-semibold text-slate-900">
                {formatMoney(inv.total_amount, inv.currency)}
              </span>
              <span className="flex w-36 shrink-0 justify-end">
                <InvoiceStateBadge processing={inv.processing_status} decision={inv.decision_status} />
              </span>
              <ChevronRight className="h-4 w-4 shrink-0 text-slate-300 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-indigo-500" />
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

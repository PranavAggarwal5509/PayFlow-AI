"use client";

import { Search, SlidersHorizontal, X } from "lucide-react";
import { useState } from "react";

import { Input, Select } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { Vendor } from "@/types/api";

export interface InvoiceFilterValues extends Record<string, string> {
  q: string;
  source_origin: string;
  decision_status: string;
  processing_status: string;
  vendor_id: string;
  currency: string;
  date_from: string;
  date_to: string;
  min_amount: string;
  max_amount: string;
}

export const EMPTY_INVOICE_FILTERS: InvoiceFilterValues = {
  q: "",
  source_origin: "ALL",
  decision_status: "",
  processing_status: "",
  vendor_id: "",
  currency: "",
  date_from: "",
  date_to: "",
  min_amount: "",
  max_amount: "",
};

const TABS = [
  { label: "All", decision: "", processing: "" },
  { label: "Approved", decision: "APPROVED", processing: "", dot: "bg-emerald-500" },
  { label: "Needs review", decision: "NEEDS_REVIEW", processing: "", dot: "bg-amber-500" },
  { label: "Rejected", decision: "REJECTED", processing: "", dot: "bg-rose-500" },
  { label: "Failed", decision: "", processing: "FAILED", dot: "bg-slate-400" },
];

const ADVANCED: (keyof InvoiceFilterValues)[] = ["vendor_id", "currency", "date_from", "date_to", "min_amount", "max_amount"];

export function InvoiceFilters({
  values,
  onChange,
  onClear,
  active,
  vendors,
}: {
  values: InvoiceFilterValues;
  onChange: (key: keyof InvoiceFilterValues, value: string) => void;
  onClear: () => void;
  active: boolean;
  vendors: Vendor[];
}) {
  const advancedCount = ADVANCED.filter((key) => values[key] !== "").length;
  const [open, setOpen] = useState(advancedCount > 0);
  const current = TABS.find((t) => t.decision === values.decision_status && t.processing === values.processing_status);

  return (
    <div className="border-b border-slate-100">
      <div className="flex flex-wrap items-center gap-3 p-4">
        <div className="flex rounded-lg bg-slate-100 p-1" role="tablist" aria-label="Decision">
          {TABS.map((tab) => {
            const selected = current?.label === tab.label;
            return (
              <button
                key={tab.label}
                type="button"
                role="tab"
                aria-selected={selected}
                onClick={() => {
                  onChange("decision_status", tab.decision);
                  onChange("processing_status", tab.processing);
                }}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[13px] font-medium transition-all",
                  selected ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-800",
                )}
              >
                {tab.dot && <span className={cn("h-1.5 w-1.5 rounded-full", tab.dot)} />}
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <Input
            value={values.q}
            onChange={(e) => onChange("q", e.target.value)}
            placeholder="Search invoice number, vendor, PO or file…"
            aria-label="Search invoices"
            className="pl-9"
          />
        </div>

        <Select
          value={values.source_origin}
          onChange={(e) => onChange("source_origin", e.target.value)}
          aria-label="Dataset"
          className="w-auto"
        >
          <option value="ALL">All invoices</option>
          <option value="LIVE_UPLOAD">Live uploads</option>
          <option value="SEED_HISTORY">Seeded history</option>
        </Select>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className={cn(
            "inline-flex h-9 items-center gap-2 rounded-md border px-3 text-[13px] font-medium transition-colors",
            open || advancedCount ? "border-indigo-200 bg-indigo-50 text-indigo-700" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50",
          )}
        >
          <SlidersHorizontal className="h-4 w-4" /> More filters
          {advancedCount > 0 && (
            <span className="rounded-full bg-indigo-600 px-1.5 text-[11px] font-semibold text-white">{advancedCount}</span>
          )}
        </button>

        {active && (
          <button
            type="button"
            onClick={onClear}
            className="inline-flex h-9 items-center gap-1.5 rounded-md px-2.5 text-[13px] font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-800"
          >
            <X className="h-4 w-4" /> Clear
          </button>
        )}
      </div>

      {open && (
        <div className="grid grid-cols-2 gap-3 border-t border-slate-100 bg-slate-50/60 px-4 py-3 md:grid-cols-3 xl:grid-cols-6">
          <Select value={values.vendor_id} onChange={(e) => onChange("vendor_id", e.target.value)} aria-label="Vendor">
            <option value="">All vendors</option>
            {vendors.map((v) => (
              <option key={v.id} value={v.id}>
                {v.vendor_name}
              </option>
            ))}
          </Select>
          <Select value={values.currency} onChange={(e) => onChange("currency", e.target.value)} aria-label="Currency">
            <option value="">All currencies</option>
            {["INR", "USD", "EUR", "GBP", "AED", "SGD"].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </Select>
          <Input type="date" value={values.date_from} onChange={(e) => onChange("date_from", e.target.value)} aria-label="Uploaded from" />
          <Input type="date" value={values.date_to} onChange={(e) => onChange("date_to", e.target.value)} aria-label="Uploaded to" />
          <Input type="number" min={0} value={values.min_amount} onChange={(e) => onChange("min_amount", e.target.value)} placeholder="Min amount" aria-label="Minimum amount" />
          <Input type="number" min={0} value={values.max_amount} onChange={(e) => onChange("max_amount", e.target.value)} placeholder="Max amount" aria-label="Maximum amount" />
        </div>
      )}
    </div>
  );
}

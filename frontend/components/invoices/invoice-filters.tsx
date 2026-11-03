"use client";

import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/input";
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
  source_origin: "LIVE_UPLOAD",
  decision_status: "",
  processing_status: "",
  vendor_id: "",
  currency: "",
  date_from: "",
  date_to: "",
  min_amount: "",
  max_amount: "",
};

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
  return (
    <div className="grid grid-cols-2 gap-3 border-b p-4 md:grid-cols-4 xl:grid-cols-5">
      <Input
        value={values.q}
        onChange={(e) => onChange("q", e.target.value)}
        placeholder="Search number, vendor, PO, file…"
        aria-label="Search invoices"
        className="col-span-2"
      />
      <Select
        value={values.source_origin}
        onChange={(e) => onChange("source_origin", e.target.value)}
        aria-label="Dataset Source"
        className="font-medium"
      >
        <option value="LIVE_UPLOAD">Live uploads</option>
        <option value="SEED_HISTORY">Historical invoices</option>
        <option value="ALL">All invoices</option>
      </Select>
      <Select value={values.decision_status} onChange={(e) => onChange("decision_status", e.target.value)} aria-label="Decision">
        <option value="">All decisions</option>
        <option value="APPROVED">Approved</option>
        <option value="NEEDS_REVIEW">Needs review</option>
        <option value="REJECTED">Rejected</option>
      </Select>
      <Select value={values.processing_status} onChange={(e) => onChange("processing_status", e.target.value)} aria-label="Processing status">
        <option value="">All processing states</option>
        <option value="PROCESSING">Processing</option>
        <option value="COMPLETED">Completed</option>
        <option value="FAILED">Failed</option>
      </Select>
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
      {active && (
        <Button variant="ghost" onClick={onClear}>
          <X className="h-4 w-4" /> Clear filters
        </Button>
      )}
    </div>
  );
}


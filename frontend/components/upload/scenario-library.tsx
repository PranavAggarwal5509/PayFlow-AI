"use client";

import { AlertTriangle, Ban, CheckCircle2, Loader2, Play, XCircle } from "lucide-react";
import { useState } from "react";

import { SAMPLE_INVOICES, type SampleInvoiceMeta } from "@/lib/samples";
import { cn } from "@/lib/utils";

const OUTCOME: Record<SampleInvoiceMeta["expected_outcome"], { label: string; icon: typeof CheckCircle2; className: string }> = {
  APPROVED: { label: "Approve", icon: CheckCircle2, className: "text-emerald-700 bg-emerald-50 ring-emerald-200" },
  NEEDS_REVIEW: { label: "Review", icon: AlertTriangle, className: "text-amber-800 bg-amber-50 ring-amber-200" },
  REJECTED: { label: "Reject", icon: XCircle, className: "text-rose-700 bg-rose-50 ring-rose-200" },
  PROCESSING_FAILED: { label: "Tech. failure", icon: Ban, className: "text-slate-700 bg-slate-100 ring-slate-200" },
};

const PREFERRED_ORDER = ["Happy path", "Duplicates", "Fraud controls", "Vendor controls", "PO controls", "Approval authority", "Data quality", "Technical failure"];
/** Preferred groups first; any new category from the generated sample list is appended, never hidden. */
const GROUP_ORDER = [
  ...PREFERRED_ORDER,
  ...Array.from(new Set(SAMPLE_INVOICES.map((s) => s.edge_case_category))).filter((g) => !PREFERRED_ORDER.includes(g)),
];

export async function loadSample(sample: SampleInvoiceMeta): Promise<File> {
  const res = await fetch(`/samples/${sample.file}`);
  if (!res.ok) throw new Error(`Could not load ${sample.file}`);
  const blob = await res.blob();
  return new File([blob], sample.file, { type: "application/pdf" });
}

/** One-click scenario runner for demos: every card is a real PDF pushed through the real pipeline. */
export function ScenarioLibrary({
  disabled,
  onLoad,
  onRun,
}: {
  disabled?: boolean;
  onLoad: (file: File, meta: SampleInvoiceMeta) => void;
  onRun: (file: File, meta: SampleInvoiceMeta) => Promise<void>;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("All");
  const groups = GROUP_ORDER.filter((g) => SAMPLE_INVOICES.some((s) => s.edge_case_category === g));
  const visible = filter === "All" ? groups : groups.filter((g) => g === filter);

  const act = async (sample: SampleInvoiceMeta, run: boolean) => {
    setBusy(sample.file);
    try {
      const file = await loadSample(sample);
      if (run) await onRun(file, sample);
      else onLoad(file, sample);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-wrap gap-1.5 border-b border-slate-100 px-5 py-3">
        {["All", ...groups].map((g) => (
          <button
            key={g}
            type="button"
            onClick={() => setFilter(g)}
            className={cn(
              "rounded-full px-2.5 py-1 text-[12px] font-medium transition-colors",
              filter === g ? "bg-navy-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200",
            )}
          >
            {g}
          </button>
        ))}
      </div>
      <div className="max-h-[640px] flex-1 space-y-5 overflow-y-auto px-5 py-4">
        {visible.map((group) => (
          <section key={group}>
            <p className="eyebrow mb-2">{group}</p>
            <ul className="space-y-2">
              {SAMPLE_INVOICES.filter((s) => s.edge_case_category === group).map((sample) => {
                const outcome = OUTCOME[sample.expected_outcome];
                const Icon = outcome.icon;
                const loading = busy === sample.file;
                return (
                  <li
                    key={sample.file}
                    className="group rounded-lg border border-slate-200 bg-white p-3 transition-all duration-150 hover:border-indigo-300 hover:shadow-lift"
                  >
                    <div className="flex items-start gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h4 className="text-[13.5px] font-semibold text-slate-900">{sample.scenario}</h4>
                          <span
                            className={cn(
                              "inline-flex items-center gap-1 rounded-full px-1.5 py-px text-[10.5px] font-semibold ring-1 ring-inset",
                              outcome.className,
                            )}
                            title="Expected outcome"
                          >
                            <Icon className="h-3 w-3" /> {outcome.label}
                          </span>
                        </div>
                        <p className="mt-1 text-[12.5px] leading-relaxed text-slate-500">{sample.description}</p>
                        <p className="mt-1.5 font-mono text-[11px] text-slate-400">{sample.file}</p>
                      </div>
                      <div className="flex shrink-0 flex-col gap-1.5">
                        <button
                          type="button"
                          disabled={disabled || !!busy}
                          onClick={() => act(sample, true)}
                          className="inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-2.5 py-1.5 text-[12px] font-semibold text-white shadow-sm transition-colors hover:bg-indigo-700 disabled:opacity-50"
                          aria-label={`Run scenario: ${sample.scenario}`}
                        >
                          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5 fill-current" />}
                          Run
                        </button>
                        <button
                          type="button"
                          disabled={disabled || !!busy}
                          onClick={() => act(sample, false)}
                          className="rounded-md px-2.5 py-1 text-[12px] font-medium text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800 disabled:opacity-50"
                        >
                          Load
                        </button>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}


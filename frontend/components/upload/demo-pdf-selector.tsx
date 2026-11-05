"use client";

import { useState } from "react";
import { ChevronDown, FileCheck, FileText, Sparkles, AlertTriangle, XCircle, CheckCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SAMPLE_INVOICES, type SampleInvoiceMeta } from "@/lib/samples";
import { DECISION_META } from "@/lib/status";
import { cn } from "@/lib/utils";

interface DemoPdfSelectorProps {
  onSelectSample: (file: File, meta: SampleInvoiceMeta) => void;
  disabled?: boolean;
}

export function DemoPdfSelector({ onSelectSample, disabled }: DemoPdfSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [loadingFile, setLoadingFile] = useState<string | null>(null);

  const handleSelect = async (sample: SampleInvoiceMeta) => {
    try {
      setLoadingFile(sample.file);
      // Fetch the sample PDF from public directory
      const res = await fetch(`/samples/${sample.file}`);
      if (!res.ok) {
        throw new Error(`Failed to load ${sample.file}`);
      }
      const blob = await res.blob();
      const file = new File([blob], sample.file, { type: "application/pdf" });
      onSelectSample(file, sample);
      setIsOpen(false);
    } catch (err) {
      console.error("Error loading sample invoice:", err);
    } finally {
      setLoadingFile(null);
    }
  };

  const outcomeIcon = (outcome: string) => {
    switch (outcome) {
      case "APPROVED":
        return <CheckCircle2 className="h-4 w-4 text-emerald-600" />;
      case "NEEDS_REVIEW":
        return <AlertTriangle className="h-4 w-4 text-amber-500" />;
      case "REJECTED":
        return <XCircle className="h-4 w-4 text-rose-600" />;
      default:
        return <FileText className="h-4 w-4 text-slate-400" />;
    }
  };

  return (
    <div className="w-full">
      <div className="flex items-center justify-between border-b border-slate-200 pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Demo Invoices & Scenarios</h3>
            <p className="text-xs text-slate-500">Pick a pre-configured PDF to test standard flows and edge cases</p>
          </div>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => setIsOpen(!isOpen)}
          className="gap-2 text-xs font-medium"
        >
          {isOpen ? "Hide Demo Invoices" : "Choose Demo Invoice"}
          <ChevronDown className={cn("h-3.5 w-3.5 transition-transform duration-200", isOpen && "rotate-180")} />
        </Button>
      </div>

      {isOpen && (
        <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          {SAMPLE_INVOICES.map((sample) => {
            const meta = DECISION_META[sample.expected_outcome as keyof typeof DECISION_META];
            const isLoading = loadingFile === sample.file;

            return (
              <button
                key={sample.file}
                type="button"
                disabled={disabled || isLoading}
                onClick={() => handleSelect(sample)}
                className="group relative flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-3 text-left shadow-xs transition-all hover:border-indigo-300 hover:bg-slate-50/70 hover:shadow-sm"
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-semibold tracking-wide uppercase text-indigo-600">
                      {sample.edge_case_category}
                    </span>
                    <Badge tone={meta?.tone ?? "neutral"} dot={false} className="text-[10px] px-1.5 py-0">
                      {meta?.label ?? sample.expected_outcome}
                    </Badge>
                  </div>

                  <div className="mt-1 flex items-center gap-1.5">
                    {outcomeIcon(sample.expected_outcome)}
                    <h4 className="text-sm font-medium text-slate-900 group-hover:text-indigo-600 transition-colors">
                      {sample.scenario}
                    </h4>
                  </div>

                  <p className="mt-1 text-xs text-slate-500 line-clamp-2 leading-relaxed">
                    {sample.description}
                  </p>
                </div>

                <div className="mt-2.5 flex items-center justify-between border-t border-slate-100 pt-2 text-[11px] text-slate-400">
                  <span className="font-mono text-slate-500">{sample.file}</span>
                  <span className="font-medium text-indigo-600 group-hover:underline">
                    {isLoading ? "Loading..." : "Load into Dropzone →"}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}


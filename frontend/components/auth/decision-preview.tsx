"use client";

import { AlertTriangle, Check, FileText, Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { usePrefersReducedMotion } from "@/hooks/use-motion";
import { cn } from "@/lib/utils";

type Verdict = "APPROVED" | "REVIEW" | "REJECTED";

interface Sample {
  vendor: string;
  number: string;
  amount: string;
  checks: { label: string; ok: boolean }[];
  verdict: Verdict;
  reason: string;
}

// Mirrors real demo scenarios (synthetic vendors).
const SAMPLES: Sample[] = [
  {
    vendor: "Acme Industrial Supplies",
    number: "ACM/2026/1042",
    amount: "₹1,14,460.00",
    checks: [
      { label: "Vendor & GSTIN verified", ok: true },
      { label: "Bank account matches master", ok: true },
      { label: "PO-2026-0001 · 3-way match", ok: true },
      { label: "No duplicates in 90 days", ok: true },
    ],
    verdict: "APPROVED",
    reason: "All 24 controls passed",
  },
  {
    vendor: "Indus Electricals",
    number: "IE/26-27/0491",
    amount: "₹17,936.00",
    checks: [
      { label: "Vendor & GSTIN verified", ok: true },
      { label: "Bank account matches master", ok: false },
      { label: "PO-2026-0009 · 3-way match", ok: true },
      { label: "No duplicates in 90 days", ok: true },
    ],
    verdict: "REVIEW",
    reason: "Bank details changed — payment held",
  },
  {
    vendor: "Falcon IT Hardware",
    number: "FIT-5702",
    amount: "₹5,06,220.00",
    checks: [
      { label: "Vendor & GSTIN verified", ok: true },
      { label: "PO-2026-0006 · 3-way match", ok: true },
      { label: "No duplicates in 90 days", ok: true },
      { label: "Within ₹4L approval authority", ok: false },
    ],
    verdict: "REVIEW",
    reason: "Above approval limit — finance sign-off",
  },
  {
    vendor: "Gamma Stationers",
    number: "GS-7802",
    amount: "₹28,320.00",
    checks: [
      { label: "Vendor is active", ok: false },
      { label: "PO-2026-0007 found", ok: true },
      { label: "Arithmetic & GST rates", ok: true },
      { label: "No duplicates in 90 days", ok: true },
    ],
    verdict: "REJECTED",
    reason: "Inactive vendor — hard stop",
  },
];

const STEP_MS = 650;
const HOLD_MS = 2600;

const VERDICT_STYLE: Record<Verdict, { label: string; className: string; icon: typeof Check }> = {
  APPROVED: { label: "Approved", className: "text-emerald-300 ring-emerald-400/50 bg-emerald-400/10", icon: Check },
  REVIEW: { label: "Needs review", className: "text-amber-300 ring-amber-400/50 bg-amber-400/10", icon: AlertTriangle },
  REJECTED: { label: "Rejected", className: "text-rose-300 ring-rose-400/50 bg-rose-400/10", icon: X },
};

/** A self-playing miniature of the real pipeline: checks tick in, then the decision is stamped. */
export function DecisionPreview() {
  const reduced = usePrefersReducedMotion();
  const [index, setIndex] = useState(0);
  const [step, setStep] = useState(0); // 0..checks.length = checks revealed, +1 = verdict

  const sample = SAMPLES[index];
  const total = sample.checks.length;

  useEffect(() => {
    if (reduced) {
      setStep(total + 1);
      return;
    }
    const done = step > total;
    const timer = setTimeout(
      () => {
        if (done) {
          setIndex((i) => (i + 1) % SAMPLES.length);
          setStep(0);
        } else setStep((s) => s + 1);
      },
      done ? HOLD_MS : STEP_MS,
    );
    return () => clearTimeout(timer);
  }, [step, total, reduced]);

  const verdict = VERDICT_STYLE[sample.verdict];
  const VerdictIcon = verdict.icon;
  const showVerdict = step > total;

  return (
    <div className="w-full max-w-xl" aria-hidden>
      <div className="glass relative overflow-hidden rounded-2xl p-5 shadow-[0_30px_80px_-30px_rgba(79,70,229,0.7)]">
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/10 text-indigo-200">
              <FileText className="h-5 w-5" />
            </span>
            <div key={sample.number} className="min-w-0 animate-fade-up">
              <p className="truncate text-[14px] font-semibold text-white">{sample.vendor}</p>
              <p className="truncate text-[12px] text-slate-400">
                {sample.number} · <span className="tabular text-slate-200">{sample.amount}</span>
              </p>
            </div>
          </div>
          <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-white/10 px-2.5 py-1 text-[11px] font-semibold text-slate-200">
            {showVerdict ? (
              <>Decided</>
            ) : (
              <>
                <Loader2 className="h-3 w-3 animate-spin" /> Verifying
              </>
            )}
          </span>
        </div>

        <div className="mt-4 h-1 overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-gradient-to-r from-indigo-400 to-emerald-400 transition-[width] duration-500 ease-out"
            style={{ width: `${(Math.min(step, total + 1) / (total + 1)) * 100}%` }}
          />
        </div>

        <ul className="mt-4 space-y-2">
          {sample.checks.map((check, i) => {
            const visible = step > i;
            return (
              <li
                key={`${sample.number}-${check.label}`}
                className={cn(
                  "flex items-center gap-2.5 text-[13px] transition-all duration-300",
                  visible ? "translate-x-0 opacity-100" : "-translate-x-2 opacity-0",
                )}
              >
                <span
                  className={cn(
                    "flex h-5 w-5 items-center justify-center rounded-full",
                    check.ok ? "bg-emerald-400/15 text-emerald-300" : "bg-amber-400/15 text-amber-300",
                  )}
                >
                  {check.ok ? <Check className="h-3 w-3" strokeWidth={3} /> : <AlertTriangle className="h-3 w-3" />}
                </span>
                <span className={check.ok ? "text-slate-300" : "font-medium text-amber-200"}>{check.label}</span>
              </li>
            );
          })}
        </ul>

        <div className="mt-4 flex min-h-[44px] items-center justify-between gap-3 border-t border-white/10 pt-4">
          <p className={cn("text-[13px] text-slate-300 transition-opacity duration-300", showVerdict ? "opacity-100" : "opacity-0")}>
            {sample.reason}
          </p>
          {showVerdict && (
            <span
              key={`${sample.number}-stamp`}
              className={cn("stamp inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[13px] font-bold uppercase tracking-wider ring-2", verdict.className)}
            >
              <VerdictIcon className="h-4 w-4" strokeWidth={3} /> {verdict.label}
            </span>
          )}
        </div>
      </div>
      <div className="mt-3 flex justify-center gap-1.5">
        {SAMPLES.map((s, i) => (
          <span key={s.number} className={cn("h-1.5 rounded-full transition-all duration-300", i === index ? "w-6 bg-white/80" : "w-1.5 bg-white/25")} />
        ))}
      </div>
    </div>
  );
}

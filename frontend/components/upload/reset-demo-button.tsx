"use client";

import { Database, Loader2, RotateCcw, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Can } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api";
import { P } from "@/lib/permissions";
import { demoService, type ResetSummary } from "@/services";

const ROWS: { key: keyof ResetSummary; label: string }[] = [
  { key: "invoices", label: "Live demo invoices" },
  { key: "runs", label: "Processing runs" },
  { key: "checks", label: "Check results" },
  { key: "decisions", label: "Decisions" },
  { key: "reviews", label: "Review-queue items" },
  { key: "po_allocations", label: "PO balance reservations" },
  { key: "email_drafts", label: "Clarification email drafts" },
  { key: "audit_entries", label: "Audit entries for those runs" },
  { key: "files", label: "Stored PDF files" },
];

/** Admin-only: wipe live demo uploads so every scenario can be run again from scratch. */
export function ResetDemoButton({ onDone }: { onDone?: () => void }) {
  return (
    <Can permission={P.DEMO_RESET}>
      <ResetDemoInner onDone={onDone} />
    </Can>
  );
}

function ResetDemoInner({ onDone }: { onDone?: () => void }) {
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<ResetSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [resetting, setResetting] = useState(false);

  const openDialog = async () => {
    setOpen(true);
    setPreview(null);
    setLoading(true);
    try {
      setPreview(await demoService.preview());
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not load the reset preview.");
      setOpen(false);
    } finally {
      setLoading(false);
    }
  };

  const confirm = async () => {
    setResetting(true);
    try {
      const result = await demoService.reset();
      toast.success("Demo reset — ready for a fresh run", {
        description: `Removed ${result.invoices} invoice(s) and ${result.runs} run(s). ${result.seeded_invoices_kept} seeded history invoices kept.`,
      });
      setOpen(false);
      window.dispatchEvent(new Event("payflow:data-changed"));
      onDone?.();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "The reset failed. Nothing was deleted.");
    } finally {
      setResetting(false);
    }
  };

  const empty = preview !== null && preview.invoices === 0;

  return (
    <>
      <button
        type="button"
        onClick={openDialog}
        className="glass inline-flex h-10 items-center gap-2 rounded-xl px-4 text-[13.5px] font-medium text-slate-100 transition-colors hover:bg-white/10"
      >
        <RotateCcw className="h-4 w-4" /> Reset demo
      </button>

      <Dialog open={open} onOpenChange={(next) => !resetting && setOpen(next)}>
        <DialogContent
          title="Reset the demo workspace?"
          description="Removes every invoice processed in this demo so all scenarios can be run again as if new. This cannot be undone."
          className="max-w-md"
        >
          <div className="rounded-xl border border-rose-100 bg-rose-50/50 p-3">
            <p className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wider text-rose-700">
              <Trash2 className="h-3.5 w-3.5" /> Will be deleted
            </p>
            {loading || !preview ? (
              <div className="mt-3 space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-4 w-full" />
                ))}
              </div>
            ) : (
              <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-[13px]">
                {ROWS.map((row) => (
                  <div key={row.key} className="contents">
                    <dt className="text-slate-600">{row.label}</dt>
                    <dd className="tabular text-right font-semibold text-slate-900">{preview[row.key]}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>

          <div className="mt-3 rounded-xl border border-emerald-100 bg-emerald-50/50 p-3">
            <p className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wider text-emerald-700">
              <ShieldCheck className="h-3.5 w-3.5" /> Kept as is
            </p>
            <p className="mt-1.5 flex items-start gap-2 text-[13px] text-slate-600">
              <Database className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
              <span>
                {preview ? <strong className="text-slate-800">{preview.seeded_invoices_kept} seeded history invoices</strong> : "Seeded history"},
                vendors, purchase orders, users and all control settings.
              </span>
            </p>
          </div>

          {empty && <p className="mt-3 text-[13px] text-slate-500">There is nothing to reset — no live demo invoices yet.</p>}

          <div className="mt-5 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setOpen(false)} disabled={resetting}>
              Cancel
            </Button>
            <Button type="button" variant="danger" onClick={confirm} disabled={resetting || loading || empty}>
              {resetting ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
              {resetting ? "Resetting…" : "Reset demo data"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

import { CheckCircle2, CircleDashed, Eye, OctagonAlert, TriangleAlert } from "lucide-react";

import { CheckBadge } from "@/components/invoices/status-badges";
import { Card, CardBody } from "@/components/ui/card";
import { evidenceFor, type EvidenceItem } from "@/lib/evidence";
import { DECISION_META } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { Decision, ValidationResult, VisualEvidence } from "@/types/api";

interface ShowProps {
  visualEvidence?: VisualEvidence | null;
  onShow?: (items: EvidenceItem[]) => void;
}

/** "Show in PDF" for a check: highlights every printed value the control looked at. */
export function ShowInPdf({ code, visualEvidence, onShow }: ShowProps & { code: string }) {
  const items = evidenceFor(visualEvidence, code);
  if (!onShow || items.length === 0) return null;
  return (
    <button
      type="button"
      onClick={() => onShow(items)}
      className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11.5px] font-semibold text-indigo-600 ring-1 ring-inset ring-indigo-200 transition-colors hover:bg-indigo-50"
      title={`Highlight ${items.map((i) => i.label.toLowerCase()).join(", ")} on the PDF`}
    >
      <Eye className="h-3 w-3" /> Show in PDF
    </button>
  );
}

const BANNER = {
  APPROVED: {
    box: "from-emerald-50 to-white ring-emerald-200",
    icon: "bg-emerald-500",
    title: "text-emerald-900",
    label: "Approved for payment",
    sub: "Every control passed and the PO balance was reserved.",
    Icon: CheckCircle2,
  },
  NEEDS_REVIEW: {
    box: "from-amber-50 to-white ring-amber-200",
    icon: "bg-amber-500",
    title: "text-amber-900",
    label: "Needs human review",
    sub: "Nothing is paid until a reviewer resolves the flags below.",
    Icon: TriangleAlert,
  },
  REJECTED: {
    box: "from-rose-50 to-white ring-rose-200",
    icon: "bg-rose-500",
    title: "text-rose-900",
    label: "Rejected",
    sub: "A hard-stop rule failed; the invoice cannot be paid as submitted.",
    Icon: OctagonAlert,
  },
} as const;

export function DecisionPanel({ decision, visualEvidence, onShow }: ShowProps & { decision: Decision | null }) {
  if (!decision) return null;
  const style = BANNER[decision.status];
  const problems = decision.reasons.filter((r) => r.severity !== "INFO");
  const passes = decision.reasons.filter((r) => r.severity === "INFO");
  return (
    <div className={cn("rounded-xl bg-gradient-to-b p-5 shadow-card ring-1 ring-inset", style.box)} data-testid="decision-panel">
      <p className="eyebrow">Decision · {DECISION_META[decision.status].label}</p>
      <div className="mt-3 flex items-center gap-3">
        <span className={cn("flex h-11 w-11 items-center justify-center rounded-full text-white shadow-sm", style.icon)}>
          <style.Icon className="h-6 w-6" />
        </span>
        <div>
          <p className={cn("text-[18px] font-semibold tracking-tight", style.title)}>{style.label}</p>
          <p className="text-[12.5px] text-slate-600">{style.sub}</p>
        </div>
      </div>
      {problems.length > 0 && (
        <ul className="mt-4 space-y-2">
          {problems.map((reason, i) => (
            <li key={`${reason.code}-${i}`} className="rounded-lg bg-white/80 p-3 ring-1 ring-inset ring-slate-200/80">
              <div className="flex items-center justify-between gap-2">
                <span
                  className={cn(
                    "rounded px-1.5 py-px text-[10px] font-semibold uppercase tracking-wide",
                    reason.severity === "BLOCKING" ? "bg-rose-100 text-rose-700" : "bg-amber-100 text-amber-800",
                  )}
                >
                  {reason.severity === "BLOCKING" ? "Blocking" : "Warning"}
                </span>
                <ShowInPdf code={reason.code} visualEvidence={visualEvidence} onShow={onShow} />
              </div>
              <p className="mt-1.5 text-[13px] leading-relaxed text-slate-700">{reason.message}</p>
            </li>
          ))}
        </ul>
      )}
      {passes.length > 0 && (
        <details className="mt-4 text-[13px] text-slate-600">
          <summary className="cursor-pointer select-none font-medium text-slate-700">
            {passes.length} controls passed
          </summary>
          <ul className="mt-2 space-y-1">
            {passes.map((reason, i) => (
              <li key={`${reason.code}-${i}`} className="flex gap-2">
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
                {reason.message}
              </li>
            ))}
          </ul>
        </details>
      )}
      <p className="mt-4 border-t border-slate-200/70 pt-3 text-[11.5px] text-slate-500">
        Decided by deterministic business rules from the validation results — the AI only extracted the data.
      </p>
    </div>
  );
}

const ICON = {
  PASSED: <CheckCircle2 className="h-4 w-4 text-success" />,
  WARNING: <TriangleAlert className="h-4 w-4 text-amber-500" />,
  FAILED: <OctagonAlert className="h-4 w-4 text-danger" />,
  SKIPPED: <CircleDashed className="h-4 w-4 text-slate-400" />,
} as const;

const GROUPS: { title: string; prefixes: string[] }[] = [
  { title: "Document data", prefixes: ["REQUIRED_FIELDS", "INVOICE_DATE", "CURRENCY_SUPPORTED", "AMOUNTS_VALID", "LINE_ITEMS_VALID", "EXTRACTION_QUALITY"] },
  { title: "Financial controls", prefixes: ["TOTAL_ARITHMETIC", "LINE_ITEM_MATH", "LINE_ITEMS_SUM", "TAX_RATES", "APPROVAL_LIMIT"] },
  { title: "Vendor verification", prefixes: ["VENDOR_MATCH", "VENDOR_STATUS", "VENDOR_GSTIN", "VENDOR_BANK"] },
  { title: "Purchase order", prefixes: ["PO_EXISTS", "PO_VENDOR", "PO_STATUS", "PO_CURRENCY", "PO_BALANCE", "PO_LINE_ITEMS"] },
  { title: "Duplicate detection", prefixes: ["DUP_FILE", "DUP_BUSINESS", "DUP_POTENTIAL"] },
];

export function ValidationList({ validations, visualEvidence, onShow }: ShowProps & { validations: ValidationResult[] }) {
  if (validations.length === 0)
    return <p className="p-5 text-sm text-muted-foreground">No validation results yet.</p>;
  return (
    <div className="space-y-4">
      {GROUPS.map((group) => {
        const items = group.prefixes
          .map((code) => validations.find((v) => v.validation_type === code))
          .filter((v): v is ValidationResult => !!v);
        if (items.length === 0) return null;
        return (
          <Card key={group.title}>
            <div className="border-b px-5 py-3 text-[13px] font-semibold">{group.title}</div>
            <CardBody className="divide-y p-0">
              {items.map((v) => (
                <div key={v.validation_type} className="flex gap-3 px-5 py-3.5" data-testid={`validation-${v.validation_type}`}>
                  <div className="mt-0.5">{ICON[v.status]}</div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-medium">{v.label}</p>
                      <div className="flex items-center gap-2">
                        <ShowInPdf code={v.validation_type} visualEvidence={visualEvidence} onShow={onShow} />
                        <CheckBadge status={v.status} />
                      </div>
                    </div>
                    <p className="mt-0.5 text-[13px] text-slate-600">{v.message}</p>
                    {(v.expected_value || v.actual_value) && (
                      <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-xs">
                        {v.expected_value && (
                          <div className="flex gap-1.5">
                            <dt className="text-muted-foreground">Expected</dt>
                            <dd className="tabular font-medium">{v.expected_value}</dd>
                          </div>
                        )}
                        {v.actual_value && (
                          <div className="flex gap-1.5">
                            <dt className="text-muted-foreground">Actual</dt>
                            <dd className="tabular font-medium">{v.actual_value}</dd>
                          </div>
                        )}
                      </dl>
                    )}
                  </div>
                </div>
              ))}
            </CardBody>
          </Card>
        );
      })}
    </div>
  );
}


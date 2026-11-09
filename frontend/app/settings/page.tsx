"use client";

import {
  CheckCircle2,
  Cpu,
  Database,
  FileCheck2,
  HardDrive,
  Info,
  Layers,
  Lock,
  RefreshCw,
  Server,
  Settings2,
  ShieldAlert,
  Sparkles,
  Workflow,
} from "lucide-react";

import { RoleMatrix } from "@/components/auth/role-matrix";
import { PageHeader } from "@/components/layout/page-header";
import { ErrorState } from "@/components/tables/table-states";
import { formatMoney } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useAsync } from "@/hooks/use-async";
import { settingsService } from "@/services";

function ConfigRow({
  label,
  value,
  description,
  badge,
}: {
  label: string;
  value: React.ReactNode;
  description?: string;
  badge?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between py-3 border-b border-slate-100 last:border-b-0 gap-1 sm:gap-4">
      <div>
        <dt className="text-sm font-medium text-slate-800">{label}</dt>
        {description && <p className="text-xs text-muted-foreground">{description}</p>}
      </div>
      <dd className="flex items-center gap-2">
        {value}
        {badge}
      </dd>
    </div>
  );
}

export default function SettingsPage() {
  const settings = useAsync(() => settingsService.get(), []);

  if (settings.error) {
    return <ErrorState message={settings.error} onRetry={settings.reload} />;
  }

  if (!settings.data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-20" />
        <Skeleton className="h-64" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  const s = settings.data;

  return (
    <>
      <PageHeader
        eyebrow="System"
        title="Controls & business rules"
        description="System environment parameters, deterministic matching thresholds, and pipeline configurations."
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => settings.reload()}
            className="gap-1.5"
            disabled={settings.loading}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${settings.loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        }
      />

      <div className="space-y-6">
        {/* Read-only notification banner */}
        <div className="flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50/50 p-4 text-sm text-blue-900">
          <Info className="h-5 w-5 shrink-0 text-blue-600 mt-0.5" />
          <div>
            <p className="font-semibold">Deterministic Policy & Configuration Integrity</p>
            <p className="text-xs text-blue-800 mt-0.5">
              PayFlow AI executes financial validations with strict immutability. Business thresholds
              and model parameters are defined in environment configurations to guarantee reproducible
              audit results across invoice batches.
            </p>
          </div>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Environment & Service Health */}
          <Card>
            <CardHeader
              title="System & Integrations"
              description="Connected infrastructure and orchestration engines"
            />
            <CardBody>
              <dl className="divide-y divide-slate-100">
                <ConfigRow
                  label="Environment"
                  value={<span className="font-mono text-xs uppercase">{s.environment}</span>}
                  badge={
                    <Badge tone={s.environment === "production" ? "danger" : "neutral"}>
                      {s.environment}
                    </Badge>
                  }
                />

                <ConfigRow
                  label="Execution Architecture"
                  value={<span className="font-mono text-xs">Direct In-Process Pipeline</span>}
                  description="FastAPI native background task orchestration (code-first, zero external workflow dependency)"
                  badge={<Badge tone="success">Native Async</Badge>}
                />

                <ConfigRow
                  label="AI Model (Extraction)"
                  value={<span className="font-mono text-xs">{s.llm_model}</span>}
                  description="Used strictly for document OCR to JSON extraction"
                  badge={
                    s.llm_configured ? (
                      <Badge tone="success">Connected</Badge>
                    ) : (
                      <Badge tone="warning">Mock Fallback</Badge>
                    )
                  }
                />

                <ConfigRow
                  label="Max Upload Size"
                  value={
                    <span className="tabular font-medium text-xs">{s.max_upload_size_mb} MB</span>
                  }
                  description="Enforced on client dropzone and server HTTP multipart"
                />

                <ConfigRow
                  label="Supported Currencies"
                  value={
                    <div className="flex flex-wrap gap-1">
                      {s.supported_currencies.map((curr) => (
                        <span
                          key={curr}
                          className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-slate-700"
                        >
                          {curr}
                        </span>
                      ))}
                    </div>
                  }
                  description="Invoices with non-supported currencies trigger review"
                />
              </dl>
            </CardBody>
          </Card>

          {/* Business Validation Thresholds */}
          <Card>
            <CardHeader
              title="Deterministic Matching Rules"
              description="Mathematical tolerances and fuzzy reconciliation limits"
            />
            <CardBody>
              <dl className="divide-y divide-slate-100">
                <ConfigRow
                  label="INR Rounding Tolerance"
                  value={
                    <span className="font-mono text-xs font-semibold text-slate-800">
                      ± ₹{s.inr_rounding_tolerance}
                    </span>
                  }
                  description="Allowed discrepancy in paise rounding for tax calculation"
                  badge={<Badge tone="neutral">Deterministic</Badge>}
                />

                <ConfigRow
                  label="Default Rounding Tolerance"
                  value={
                    <span className="font-mono text-xs font-semibold text-slate-800">
                      ± {s.default_rounding_tolerance}
                    </span>
                  }
                  description="Tolerance for other foreign currencies (USD, EUR, GBP)"
                  badge={<Badge tone="neutral">Deterministic</Badge>}
                />

                <ConfigRow
                  label="Vendor Fuzzy Match Threshold"
                  value={
                    <span className="font-mono text-xs font-semibold text-slate-800">
                      {s.vendor_fuzzy_threshold}%
                    </span>
                  }
                  description="Token-sort ratio required to automatically resolve vendor"
                  badge={
                    <Badge tone={s.vendor_fuzzy_threshold >= 80 ? "success" : "warning"}>
                      Suggestion only
                    </Badge>
                  }
                />

                <ConfigRow
                  label="Duplicate Invoice Similarity"
                  value={
                    <span className="font-mono text-xs font-semibold text-slate-800">
                      {s.duplicate_number_similarity}%
                    </span>
                  }
                  description="Threshold for potential duplicate invoice warning"
                  badge={<Badge tone="info">Level 3</Badge>}
                />

                <ConfigRow
                  label="GSTIN Requirement"
                  value={
                    s.require_gstin_for_approval ? (
                      <span className="text-xs font-semibold text-emerald-700">Required</span>
                    ) : (
                      <span className="text-xs text-slate-500">Optional for non-taxable</span>
                    )
                  }
                  description="Mandates validated GSTIN for automated APPROVAL"
                  badge={
                    <Badge tone={s.require_gstin_for_approval ? "success" : "neutral"}>
                      {s.require_gstin_for_approval ? "Enforced" : "Relaxed"}
                    </Badge>
                  }
                />
              </dl>
            </CardBody>
          </Card>
        </div>

        {/* Enterprise payment controls */}
        <Card>
          <CardHeader
            title="Payment & fraud controls"
            description="Policies applied on top of matching — each one produces an explainable check result"
          />
          <CardBody>
            <dl className="grid gap-x-8 divide-y divide-slate-100 md:grid-cols-2 md:divide-y-0">
              <ConfigRow
                label="Auto-approval authority limit"
                value={
                  <span className="font-mono text-xs font-semibold text-slate-800">
                    {formatMoney(s.auto_approval_limit_inr, "INR")}
                  </span>
                }
                description="Invoices above this INR-equivalent value always need a named finance approver"
                badge={<Badge tone="warning">Delegation of authority</Badge>}
              />
              <ConfigRow
                label="Bank account verification"
                value={<span className="text-xs font-semibold text-emerald-700">Always on</span>}
                description="Remittance details on the invoice must match the verified vendor master, or payment is held"
                badge={<Badge tone="danger">Fraud</Badge>}
              />
              <ConfigRow
                label="GSTIN checksum"
                value={<span className="text-xs font-semibold text-emerald-700">GSTN mod-36</span>}
                description="Catches typos, OCR misreads and fabricated registrations before matching"
                badge={<Badge tone="success">Tax</Badge>}
              />
              <ConfigRow
                label="Valid GST slabs"
                value={
                  <div className="flex flex-wrap justify-end gap-1">
                    {(s.valid_gst_rates ?? []).map((rate) => (
                      <span key={rate} className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-slate-700">
                        {rate}%
                      </span>
                    ))}
                  </div>
                }
                description="Line tax rates outside notified slabs, or tax that does not match line rates, are flagged"
                badge={<Badge tone="success">Tax</Badge>}
              />
              <ConfigRow
                label="Potential-duplicate window"
                value={<span className="font-mono text-xs font-semibold text-slate-800">{s.duplicate_window_days} days</span>}
                description="Same vendor + same amount only counts as suspicious when invoice dates are this close"
                badge={<Badge tone="info">Duplicates</Badge>}
              />
              <ConfigRow
                label="Implied PO handling"
                value={
                  <span className="text-xs font-semibold text-slate-800">
                    {s.auto_approve_inferred_po ? "Auto-accept" : "Suggest, human confirms"}
                  </span>
                }
                description="Missing PO references are inferred from vendor + line items; a reviewer confirms by default"
                badge={<Badge tone="info">Procurement</Badge>}
              />
              <ConfigRow
                label="PO line price tolerance"
                value={
                  <span className="font-mono text-xs font-semibold text-slate-800">
                    ± {Math.round(Number(s.po_line_price_tolerance_pct ?? 0) * 100)}%
                  </span>
                }
                description="Unit price variance allowed against the PO line before a reviewer is needed"
                badge={<Badge tone="info">Procurement</Badge>}
              />
              <ConfigRow
                label="Reference FX (approval limit only)"
                value={
                  <div className="flex flex-wrap justify-end gap-1">
                    {Object.entries(s.fx_rates_to_inr ?? {}).map(([code, rate]) => (
                      <span key={code} className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-700">
                        {code} {rate}
                      </span>
                    ))}
                  </div>
                }
                description="Foreign invoices are converted only to compare against the INR authority limit"
                badge={<Badge tone="neutral">FX</Badge>}
              />
            </dl>
          </CardBody>
        </Card>

        <RoleMatrix />

        {/* Current Authenticated User Session */}
        {s.user && (
          <Card>
            <CardHeader
              title="Operator Identity & RBAC"
              description="Authenticated session context for audit logging"
            />
            <CardBody>
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="rounded-md border p-3">
                  <span className="text-xs text-muted-foreground">Operator Name</span>
                  <p className="text-sm font-semibold mt-0.5">{s.user.name}</p>
                </div>
                <div className="rounded-md border p-3">
                  <span className="text-xs text-muted-foreground">Operator ID</span>
                  <p className="font-mono text-xs text-slate-700 mt-0.5">{s.user.id}</p>
                </div>
                <div className="rounded-md border p-3">
                  <span className="text-xs text-muted-foreground">Security Role</span>
                  <div className="mt-0.5">
                    <Badge tone="info">{s.user.role.toUpperCase()}</Badge>
                  </div>
                </div>
              </div>
            </CardBody>
          </Card>
        )}
      </div>
    </>
  );
}


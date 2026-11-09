"use client";

import { useState } from "react";
import { RotateCcw } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";

import { DecisionPanel, ValidationList } from "@/components/invoices/decision-validation";
import {
  FinancialSummaryCard,
  HistoryCard,
  InvoiceInfoCard,
  LineItemsCard,
  PurchaseOrderCard,
  VendorCard,
} from "@/components/invoices/invoice-sections";
import { PdfViewer } from "@/components/invoices/pdf-viewer";
import { InvoiceStateBadge } from "@/components/invoices/status-badges";
import { PageHeader } from "@/components/layout/page-header";
import { useAuth } from "@/components/auth/auth-provider";
import { ReviewActions } from "@/components/review/review-actions";
import { ErrorState } from "@/components/tables/table-states";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAsync } from "@/hooks/use-async";
import { ApiError } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { invoiceService } from "@/services";
import type { FieldEvidence } from "@/types/api";

export default function InvoiceDetailPage() {
  const { can } = useAuth();
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: invoice, loading, error, reload } = useAsync(() => invoiceService.get(id), [id]);
  const [activeEvidence, setActiveEvidence] = useState<FieldEvidence | null>(null);
  const [activeLabel, setActiveLabel] = useState<string | null>(null);

  const handleSelectEvidence = (label: string, ev: FieldEvidence) => {
    setActiveLabel(label);
    setActiveEvidence(ev);
  };

  const handleClearEvidence = () => {
    setActiveLabel(null);
    setActiveEvidence(null);
  };

  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (loading || !invoice)
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-[640px]" />
        <div className="space-y-4">
          <Skeleton className="h-40" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );

  const latestRun = invoice.runs[invoice.runs.length - 1];
  const reviewOpen =
    invoice.review && (invoice.review.review_status === "PENDING" || invoice.review.review_status === "CLARIFICATION_REQUESTED");
  const failed = invoice.processing_status === "FAILED";

  const retry = async () => {
    try {
      const result = await invoiceService.retry(invoice.id);
      toast.success("A new processing run has started.");
      router.push(`/processing/${result.run_id}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not retry.");
    }
  };

  return (
    <>
      <PageHeader
        title={invoice.invoice_number ?? "Invoice (no number)"}
        description={`${invoice.vendor_name ?? "Unknown vendor"} · ${formatMoney(invoice.total_amount, invoice.currency)}`}
        actions={
          <>
            <InvoiceStateBadge processing={invoice.processing_status} decision={invoice.decision_status} />
            {latestRun && (
              <Button asChild variant="outline" size="sm">
                <Link href={`/processing/${latestRun.id}`}>View processing</Link>
              </Button>
            )}
            {failed && can("invoices:upload") && (
              <Button size="sm" onClick={retry}>
                <RotateCcw className="h-4 w-4" /> Retry
              </Button>
            )}
          </>
        }
      />

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <div className="xl:sticky xl:top-20 xl:h-[calc(100vh-7rem)]">
          <PdfViewer
            invoiceId={invoice.id}
            pageCount={invoice.page_count}
            visualEvidence={invoice.visual_evidence}
            activeEvidence={activeEvidence}
            activeFieldLabel={activeLabel}
            onClearEvidence={handleClearEvidence}
          />
        </div>

        <div className="space-y-4">
          {failed && (
            <Card className="border-danger-ring bg-danger-soft/50">
              <CardBody>
                <p className="text-sm font-semibold text-danger">Processing failed — not rejected</p>
                <p className="mt-1 text-[13px]">{invoice.error_message}</p>
              </CardBody>
            </Card>
          )}
          <DecisionPanel decision={invoice.decision} />

          {reviewOpen && invoice.review && (
            <Card>
              <CardBody className="space-y-3">
                <div>
                  <p className="text-sm font-semibold">Manual review required</p>
                  <p className="text-[13px] text-muted-foreground">
                    {invoice.review.review_status === "CLARIFICATION_REQUESTED"
                      ? "Clarification has been requested. You can still make a final decision."
                      : "Inspect the checks below, then decide."}
                  </p>
                </div>
                <ReviewActions reviewId={invoice.review.id} invoiceLabel={invoice.invoice_number ?? "invoice"} onDone={reload} />
              </CardBody>
            </Card>
          )}
          {invoice.review && !reviewOpen && invoice.review.reviewer_comment && (
            <Card>
              <CardBody>
                <p className="text-xs text-muted-foreground">Manual decision by {invoice.review.assigned_to}</p>
                <p className="mt-1 text-sm">“{invoice.review.reviewer_comment}”</p>
              </CardBody>
            </Card>
          )}

          <Tabs defaultValue="details">
            <TabsList>
              <TabsTrigger value="details">Details</TabsTrigger>
              <TabsTrigger value="validations">Validations ({invoice.validations.length})</TabsTrigger>
              <TabsTrigger value="history">History</TabsTrigger>
            </TabsList>
            <TabsContent value="details" className="mt-4 space-y-4">
              <InvoiceInfoCard invoice={invoice} onSelectEvidence={handleSelectEvidence} />
              <VendorCard invoice={invoice} onSelectEvidence={handleSelectEvidence} />
              <PurchaseOrderCard invoice={invoice} />
              <LineItemsCard invoice={invoice} />
              <FinancialSummaryCard invoice={invoice} onSelectEvidence={handleSelectEvidence} />
            </TabsContent>
            <TabsContent value="validations" className="mt-4">
              <ValidationList validations={invoice.validations} />
            </TabsContent>
            <TabsContent value="history" className="mt-4">
              <HistoryCard invoice={invoice} />
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </>
  );
}


"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Check, Eye, MessageSquareQuote, X } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { useAuth } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { FieldError, Label, Textarea } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { reviewService } from "@/services";
import type { ReviewAction } from "@/types/api";

/** Mirrors the API rule: every decision needs a written reason (whitespace does not count). */
export const MIN_REASON = 10;
const normalise = (text: string) => text.split(/\s+/).filter(Boolean).join(" ");

const schema = z.object({
  comment: z
    .string()
    .max(2000)
    .refine((v) => normalise(v).length >= MIN_REASON, `Write at least ${MIN_REASON} characters explaining this decision.`),
});
type Form = z.infer<typeof schema>;

const COPY: Record<
  ReviewAction,
  { title: string; verb: string; description: string; variant: "success" | "danger" | "default"; label: string; placeholder: string }
> = {
  APPROVE: {
    title: "Approve invoice",
    verb: "Approve invoice",
    description: "The invoice will be marked APPROVED and its amount reserved against the purchase order.",
    variant: "success",
    label: "Why is it safe to approve?",
    placeholder: "e.g. Confirmed the new bank account with the vendor by phone on the number in the master.",
  },
  REJECT: {
    title: "Reject invoice",
    verb: "Reject invoice",
    description: "The invoice will be marked REJECTED. This is recorded in the audit log.",
    variant: "danger",
    label: "Why is it being rejected?",
    placeholder: "e.g. Duplicate of ACM/2026/1042 already paid against PO-2026-0001.",
  },
  REQUEST_CLARIFICATION: {
    title: "Request clarification",
    verb: "Create clarification email",
    description: "An email draft is created for the vendor with your question. Nothing is sent automatically.",
    variant: "default",
    label: "What should the vendor clarify?",
    placeholder: "e.g. Please confirm the PO number for this invoice and resend with it printed.",
  },
};

export function ReviewActions({
  reviewId,
  invoiceLabel,
  onDone,
  size = "default",
}: {
  reviewId: string;
  invoiceLabel: string;
  onDone: () => void;
  size?: "default" | "sm";
}) {
  const { can, user } = useAuth();
  const [action, setAction] = useState<ReviewAction | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const form = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { comment: "" }, mode: "onChange" });
  const typed = normalise(form.watch("comment") ?? "").length;
  const ready = typed >= MIN_REASON;

  const close = () => {
    setAction(null);
    form.reset();
  };

  const submit = form.handleSubmit(async ({ comment }) => {
    if (!action) return;
    setSubmitting(true);
    try {
      await reviewService.decide(reviewId, action, normalise(comment));
      toast.success(
        action === "APPROVE" ? "Invoice approved." : action === "REJECT" ? "Invoice rejected." : "Clarification requested.",
      );
      close();
      onDone();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "The decision could not be saved.");
    } finally {
      setSubmitting(false);
    }
  });

  const copy = action ? COPY[action] : null;
  if (!can("review:act")) {
    return (
      <span
        title={`${user?.role_label ?? "Your role"} can view decisions but not change them`}
        className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full bg-slate-100 px-2.5 py-1 text-[12px] font-medium text-slate-500 ring-1 ring-inset ring-slate-200"
      >
        <Eye className="h-3.5 w-3.5" /> View only
      </span>
    );
  }
  return (
    <>
      <div className={size === "sm" ? "flex w-[190px] flex-wrap gap-1.5" : "flex flex-wrap gap-2"}>
        <Button size={size} variant="success" onClick={() => setAction("APPROVE")}>
          <Check className="h-4 w-4" /> Approve
        </Button>
        <Button size={size} variant="danger" onClick={() => setAction("REJECT")}>
          <X className="h-4 w-4" /> Reject
        </Button>
        <Button size={size} variant="outline" onClick={() => setAction("REQUEST_CLARIFICATION")}>
          <MessageSquareQuote className="h-4 w-4" /> {size === "sm" ? "Clarify" : "Request clarification"}
        </Button>
      </div>

      <Dialog open={action !== null} onOpenChange={(open) => !open && close()}>
        {copy && (
          <DialogContent title={`${copy.title} — ${invoiceLabel}`} description={copy.description}>
            <form onSubmit={submit} noValidate>
              <Label htmlFor="review-comment">
                {copy.label} <span className="text-rose-600">*</span>
              </Label>
              <Textarea
                id="review-comment"
                autoFocus
                rows={4}
                placeholder={copy.placeholder}
                aria-describedby="review-comment-hint"
                aria-invalid={!!form.formState.errors.comment}
                {...form.register("comment")}
              />
              <div id="review-comment-hint" className="mt-1.5 flex items-center justify-between gap-3 text-[12px]">
                <span className={ready ? "text-emerald-700" : "text-slate-500"}>
                  {ready
                    ? "Reason recorded in the audit log with your name."
                    : `A written reason is required — ${MIN_REASON - typed} more character${MIN_REASON - typed === 1 ? "" : "s"}.`}
                </span>
                <span className="tabular text-slate-400">{typed}/2000</span>
              </div>
              <FieldError message={form.formState.isSubmitted ? form.formState.errors.comment?.message : undefined} />
              <div className="mt-5 flex justify-end gap-2">
                <Button type="button" variant="ghost" onClick={close} disabled={submitting}>
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant={copy.variant}
                  disabled={submitting || !ready}
                  title={ready ? undefined : "Write a reason first"}
                >
                  {submitting ? "Saving…" : `Confirm: ${copy.verb}`}
                </Button>
              </div>
            </form>
          </DialogContent>
        )}
      </Dialog>
    </>
  );
}


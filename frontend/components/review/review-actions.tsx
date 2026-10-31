"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Check, MessageSquareQuote, X } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { FieldError, Label, Textarea } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { reviewService } from "@/services";
import type { ReviewAction } from "@/types/api";

const schema = z.object({
  comment: z.string().trim().min(3, "Please add a comment (at least 3 characters).").max(2000),
});
type Form = z.infer<typeof schema>;

const COPY: Record<ReviewAction, { title: string; verb: string; description: string; variant: "success" | "danger" | "default" }> = {
  APPROVE: {
    title: "Approve invoice",
    verb: "Approve invoice",
    description: "The invoice will be marked APPROVED and its amount reserved against the purchase order.",
    variant: "success",
  },
  REJECT: {
    title: "Reject invoice",
    verb: "Reject invoice",
    description: "The invoice will be marked REJECTED. This is recorded in the audit log.",
    variant: "danger",
  },
  REQUEST_CLARIFICATION: {
    title: "Request clarification",
    verb: "Create clarification request",
    description: "A clarification email draft is created for the vendor. Nothing is sent automatically.",
    variant: "default",
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
  const [action, setAction] = useState<ReviewAction | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const form = useForm<Form>({ resolver: zodResolver(schema), defaultValues: { comment: "" } });

  const close = () => {
    setAction(null);
    form.reset();
  };

  const submit = form.handleSubmit(async ({ comment }) => {
    if (!action) return;
    setSubmitting(true);
    try {
      await reviewService.decide(reviewId, action, comment);
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
  return (
    <>
      <div className="flex flex-wrap gap-2">
        <Button size={size} variant="success" onClick={() => setAction("APPROVE")}>
          <Check className="h-4 w-4" /> Approve
        </Button>
        <Button size={size} variant="danger" onClick={() => setAction("REJECT")}>
          <X className="h-4 w-4" /> Reject
        </Button>
        <Button size={size} variant="outline" onClick={() => setAction("REQUEST_CLARIFICATION")}>
          <MessageSquareQuote className="h-4 w-4" /> Request clarification
        </Button>
      </div>

      <Dialog open={action !== null} onOpenChange={(open) => !open && close()}>
        {copy && (
          <DialogContent title={`${copy.title} — ${invoiceLabel}`} description={copy.description}>
            <form onSubmit={submit} noValidate>
              <Label htmlFor="review-comment">Reviewer comment (required)</Label>
              <Textarea id="review-comment" autoFocus placeholder="Explain the reason for this decision…" {...form.register("comment")} />
              <FieldError message={form.formState.errors.comment?.message} />
              <div className="mt-5 flex justify-end gap-2">
                <Button type="button" variant="ghost" onClick={close} disabled={submitting}>
                  Cancel
                </Button>
                <Button type="submit" variant={copy.variant} disabled={submitting}>
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


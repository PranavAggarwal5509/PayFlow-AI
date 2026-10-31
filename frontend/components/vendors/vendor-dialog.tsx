"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { FieldError, Input, Label, Select, Textarea } from "@/components/ui/input";
import { ApiError } from "@/lib/api";
import { vendorService } from "@/services";
import type { Vendor } from "@/types/api";

const GSTIN = /^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;

export const vendorSchema = z.object({
  vendor_name: z.string().trim().min(2, "Vendor name is required."),
  gstin: z
    .string()
    .trim()
    .toUpperCase()
    .refine((v) => v === "" || GSTIN.test(v), "Enter a valid 15-character GSTIN."),
  address: z.string().trim().max(500),
  email: z.string().trim().refine((v) => v === "" || z.string().email().safeParse(v).success, "Enter a valid email."),
  phone: z.string().trim().max(32),
  status: z.enum(["ACTIVE", "INACTIVE", "PENDING"]),
});
type VendorForm = z.infer<typeof vendorSchema>;

const blank: VendorForm = { vendor_name: "", gstin: "", address: "", email: "", phone: "", status: "ACTIVE" };

export function VendorDialog({
  open,
  onOpenChange,
  vendor,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  vendor?: Vendor | null;
  onSaved: () => void;
}) {
  const [saving, setSaving] = useState(false);
  const form = useForm<VendorForm>({ resolver: zodResolver(vendorSchema), defaultValues: blank });
  const { errors } = form.formState;

  useEffect(() => {
    if (open)
      form.reset(
        vendor
          ? {
              vendor_name: vendor.vendor_name,
              gstin: vendor.gstin ?? "",
              address: vendor.address ?? "",
              email: vendor.email ?? "",
              phone: vendor.phone ?? "",
              status: vendor.status,
            }
          : blank,
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, vendor]);

  const submit = form.handleSubmit(async (values) => {
    setSaving(true);
    const body = { ...values, gstin: values.gstin || null, address: values.address || null, email: values.email || null, phone: values.phone || null };
    try {
      if (vendor) await vendorService.update(vendor.id, body);
      else await vendorService.create(body);
      toast.success(vendor ? "Vendor updated." : "Vendor created.");
      onOpenChange(false);
      onSaved();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save the vendor.");
    } finally {
      setSaving(false);
    }
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={vendor ? `Edit ${vendor.vendor_code}` : "Add vendor"} description="Vendors in this register are the only ones whose invoices can be approved automatically.">
        <form onSubmit={submit} noValidate className="space-y-3">
          <div>
            <Label htmlFor="vendor_name">Vendor name</Label>
            <Input id="vendor_name" {...form.register("vendor_name")} />
            <FieldError message={errors.vendor_name?.message} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="gstin">GSTIN</Label>
              <Input id="gstin" placeholder="27AABCA1234A1Z5" {...form.register("gstin")} />
              <FieldError message={errors.gstin?.message} />
            </div>
            <div>
              <Label htmlFor="status">Status</Label>
              <Select id="status" {...form.register("status")}>
                <option value="ACTIVE">Active</option>
                <option value="INACTIVE">Inactive</option>
                <option value="PENDING">Pending</option>
              </Select>
            </div>
            <div>
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" {...form.register("email")} />
              <FieldError message={errors.email?.message} />
            </div>
            <div>
              <Label htmlFor="phone">Phone</Label>
              <Input id="phone" {...form.register("phone")} />
            </div>
          </div>
          <div>
            <Label htmlFor="address">Address</Label>
            <Textarea id="address" className="min-h-[64px]" {...form.register("address")} />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving ? "Saving…" : vendor ? "Save changes" : "Add vendor"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}


"use client";

import { PageHeader } from "@/components/layout/page-header";
import { InvoiceDropzone } from "@/components/upload/invoice-dropzone";
import { ResetDemoButton } from "@/components/upload/reset-demo-button";
import { useAsync } from "@/hooks/use-async";
import { settingsService } from "@/services";

export default function UploadPage() {
  const settings = useAsync(() => settingsService.get(), []);

  return (
    <>
      <PageHeader
        eyebrow="Accounts payable"
        title="Process an invoice"
        description="Upload a vendor PDF or run a prepared scenario. Each stage executes live, and every decision comes with its reasons."
        actions={<ResetDemoButton />}
      />
      <InvoiceDropzone maxMb={settings.data?.max_upload_size_mb ?? 15} />
    </>
  );
}

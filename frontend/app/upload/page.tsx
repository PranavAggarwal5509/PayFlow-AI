"use client";

import { InvoiceDropzone } from "@/components/upload/invoice-dropzone";
import { useAsync } from "@/hooks/use-async";
import { settingsService } from "@/services";

export default function UploadPage() {
  const settings = useAsync(() => settingsService.get(), []);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col items-center justify-center py-6 sm:py-10">
      {/* Page Heading */}
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
          Upload Invoice
        </h1>
        <p className="mt-2 text-sm text-slate-500 sm:text-base">
          Upload a PDF invoice to start automated verification.
        </p>
      </div>

      {/* Main Upload Card */}
      <div className="w-full">
        <InvoiceDropzone maxMb={settings.data?.max_upload_size_mb ?? 15} />
      </div>
    </div>
  );
}

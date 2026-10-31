"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import {
  AlertCircle,
  FileText,
  Loader2,
  Upload,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useRef, useState, type DragEvent } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import { cn } from "@/lib/utils";
import { invoiceService } from "@/services";

export const MAX_UPLOAD_MB = 15;

export function buildUploadSchema(maxMb: number) {
  return z.object({
    file: z
      .instanceof(File, { message: "Choose a PDF invoice to upload." })
      .refine(
        (f) => f.name.toLowerCase().endsWith(".pdf") && (f.type === "application/pdf" || f.type === ""),
        "Only PDF documents are accepted.",
      )
      .refine((f) => f.size > 0, "The file is empty.")
      .refine((f) => f.size <= maxMb * 1024 * 1024, `The file exceeds the ${maxMb} MB limit.`),
  });
}

type UploadForm = z.infer<ReturnType<typeof buildUploadSchema>>;

export function InvoiceDropzone({ maxMb = MAX_UPLOAD_MB }: { maxMb?: number }) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);

  const form = useForm<UploadForm>({
    resolver: zodResolver(buildUploadSchema(maxMb)),
    mode: "onChange",
  });
  const file = form.watch("file") as File | undefined;
  const error = form.formState.errors.file?.message;
  const uploading = progress !== null;

  const choose = useCallback(
    (selected: File | undefined) => {
      if (!selected) return;
      form.setValue("file", selected, { shouldValidate: true });
    },
    [form],
  );

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    choose(event.dataTransfer.files?.[0]);
  };

  const removeFile = () => {
    form.resetField("file");
    if (inputRef.current) inputRef.current.value = "";
  };

  const submit = form.handleSubmit(async ({ file: chosen }) => {
    setProgress(0);
    try {
      const result = await invoiceService.upload(chosen, setProgress);
      toast.success("Invoice uploaded. Verification pipeline started.");
      router.push(`/processing/${result.run_id}`);
    } catch (err) {
      setProgress(null);
      toast.error(err instanceof ApiError ? err.message : "Upload failed. Please try again.");
    }
  });

  return (
    <form onSubmit={submit} noValidate className="w-full">
      <Card className="border-slate-200/80 bg-white shadow-card transition-all">
        <CardBody className="p-6 sm:p-10">
          {/* Large Drag-and-drop area */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => !uploading && inputRef.current?.click()}
            className={cn(
              "group relative flex min-h-[290px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 text-center transition-all duration-200 ease-in-out sm:p-12",
              dragging
                ? "border-blue-600 bg-blue-50/70 ring-4 ring-blue-500/10"
                : "border-slate-200 bg-slate-50/50 hover:border-blue-400 hover:bg-slate-50/80",
              error && "border-rose-400 bg-rose-50/40 ring-4 ring-rose-500/10",
              file && "border-blue-200 bg-blue-50/20",
            )}
          >
            {/* Upload Icon */}
            <div
              className={cn(
                "mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-white shadow-xs ring-1 ring-slate-900/5 transition-transform duration-200 group-hover:scale-105",
                dragging && "scale-110 bg-blue-600 text-white ring-0",
                file ? "bg-blue-50 text-blue-600" : "text-blue-600",
              )}
            >
              <Upload className="h-8 w-8 stroke-[1.8]" />
            </div>

            <h3 className="text-lg font-semibold tracking-tight text-slate-900 sm:text-xl">
              Drag and drop your invoice here
            </h3>

            <p className="my-2.5 text-xs font-medium uppercase tracking-wider text-slate-400">
              or
            </p>

            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={uploading}
              onClick={(e) => {
                e.stopPropagation();
                inputRef.current?.click();
              }}
              className="border-slate-200 bg-white px-4 py-2 font-medium text-slate-700 shadow-xs hover:border-slate-300 hover:bg-slate-50"
            >
              Browse Files
            </Button>

            <input
              ref={inputRef}
              type="file"
              accept="application/pdf,.pdf"
              className="sr-only"
              data-testid="file-input"
              aria-label="Choose invoice PDF"
              onChange={(e) => {
                choose(e.target.files?.[0]);
                e.target.value = "";
              }}
            />

            <div className="mt-7 flex items-center justify-center gap-2 text-xs text-slate-500">
              <span>Supported format: <strong className="font-semibold text-slate-700">PDF</strong></span>
              <span className="text-slate-300">•</span>
              <span>Maximum file size: <strong className="font-semibold text-slate-700">{maxMb} MB</strong></span>
            </div>
          </div>

          {/* Validation Error Banner */}
          {error && (
            <div
              role="alert"
              className="mt-4 flex items-center gap-2.5 rounded-xl border border-rose-200 bg-rose-50/80 px-4 py-3 text-xs font-medium text-rose-800 shadow-2xs"
            >
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
              <span>{error}</span>
            </div>
          )}

          {/* Selected File Card */}
          {file && !error && (
            <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50/60 p-4 transition-all">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3.5 min-w-0">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-100/70 text-blue-700 shadow-2xs">
                    <FileText className="h-6 w-6" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold text-slate-900">{file.name}</p>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {formatBytes(file.size)} · PDF document ready
                    </p>
                  </div>
                </div>

                {!uploading && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    aria-label="Remove file"
                    onClick={removeFile}
                    className="h-8 w-8 text-slate-400 hover:bg-slate-200/60 hover:text-slate-700"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>

              {/* Upload Progress Indicator */}
              {uploading && (
                <div className="mt-4 border-t border-slate-200/70 pt-3">
                  <div className="mb-1.5 flex items-center justify-between text-xs font-medium text-slate-600">
                    <span>Uploading and preparing processing pipeline…</span>
                    <span className="tabular">{progress}%</span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200/80">
                    <div
                      className="h-full rounded-full bg-blue-600 transition-all duration-300"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Upload & Process Action */}
          <div className="mt-6 pt-2">
            <Button
              type="submit"
              disabled={!file || !!error || uploading}
              size="lg"
              className="w-full bg-blue-600 py-6 text-sm font-semibold tracking-wide text-white shadow-sm transition-all hover:bg-blue-700 disabled:opacity-50 sm:text-base"
            >
              {uploading ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Uploading & Processing…
                </>
              ) : (
                "Upload and Process"
              )}
            </Button>
          </div>
        </CardBody>
      </Card>
    </form>
  );
}

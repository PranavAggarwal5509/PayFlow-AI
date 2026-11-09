"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle, FileText, Library, Loader2, Lock, ShieldCheck, Upload, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { loadSample, ScenarioLibrary } from "@/components/upload/scenario-library";
import { SAMPLE_INVOICES } from "@/lib/samples";
import { ApiError } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import type { SampleInvoiceMeta } from "@/lib/samples";
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
  const [selectedDemoScenario, setSelectedDemoScenario] = useState<SampleInvoiceMeta | null>(null);

  const form = useForm<UploadForm>({
    resolver: zodResolver(buildUploadSchema(maxMb)),
    mode: "onChange",
  });
  const file = form.watch("file") as File | undefined;
  const error = form.formState.errors.file?.message;
  const uploading = progress !== null;

  const choose = useCallback(
    (selected: File | undefined, demoMeta?: SampleInvoiceMeta) => {
      if (!selected) return;
      setSelectedDemoScenario(demoMeta ?? null);
      form.setValue("file", selected, { shouldValidate: true });
    },
    [form],
  );

  // Deep link from the command palette: /upload?scenario=<file> preloads that scenario.
  useEffect(() => {
    const wanted = new URLSearchParams(window.location.search).get("scenario");
    const sample = SAMPLE_INVOICES.find((s) => s.file === wanted);
    if (sample) loadSample(sample).then((f) => choose(f, sample)).catch(() => undefined);
  }, [choose]);

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    choose(event.dataTransfer.files?.[0]);
  };

  const removeFile = () => {
    form.resetField("file");
    setSelectedDemoScenario(null);
    if (inputRef.current) inputRef.current.value = "";
  };

  const send = async (chosen: File) => {
    setProgress(0);
    try {
      const result = await invoiceService.upload(chosen, setProgress);
      toast.success("Invoice received. Verification pipeline started.");
      router.push(`/processing/${result.run_id}`);
    } catch (err) {
      setProgress(null);
      toast.error(err instanceof ApiError ? err.message : "Upload failed. Please try again.");
    }
  };

  const submit = form.handleSubmit(async ({ file: chosen }) => send(chosen));

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,460px)]">
    <form onSubmit={submit} noValidate className="w-full space-y-5">
      <Card className="bg-white shadow-card transition-all">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-6 py-4">
          <div>
            <p className="eyebrow">Intake</p>
            <h3 className="mt-0.5 text-[15px] font-semibold">Submit a vendor invoice</h3>
          </div>
          <span className="inline-flex items-center gap-1.5 text-[12px] text-slate-500">
            <Lock className="h-3.5 w-3.5" /> Stored privately · SHA-256 fingerprinted
          </span>
        </div>
        <CardBody className="p-6">
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
              "group relative flex min-h-[260px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 text-center transition-all duration-200 ease-in-out sm:p-12",
              dragging
                ? "drop-glow border-transparent bg-blue-50/70 ring-4 ring-blue-500/10"
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

            <h3 className="text-lg font-semibold tracking-tight text-slate-900">
              Drop an invoice PDF here
            </h3>
            <p className="mt-1 text-[13px] text-slate-500">Digital or scanned — the pipeline handles both.</p>

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
              Browse files
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
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-semibold text-slate-900">{file.name}</p>
                      {selectedDemoScenario && (
                        <span className="inline-flex items-center rounded-md bg-indigo-50 px-2 py-0.5 text-[10px] font-semibold text-indigo-700 ring-1 ring-inset ring-indigo-600/20">
                          {selectedDemoScenario.edge_case_category}
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 text-xs text-slate-500">
                      {formatBytes(file.size)} · PDF document ready
                      {selectedDemoScenario && ` · Expected: ${selectedDemoScenario.expected_outcome}`}
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

              {selectedDemoScenario && (
                <div className="mt-3 rounded-lg border border-indigo-100 bg-indigo-50/50 p-2.5 text-xs text-indigo-900">
                  <span className="font-semibold text-indigo-950">Scenario: </span>
                  {selectedDemoScenario.scenario} — {selectedDemoScenario.description}
                </div>
              )}

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
              className="h-11 w-full text-sm font-semibold shadow-sm"
            >
              {uploading ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Uploading & Processing…
                </>
              ) : (
                <>
                  <ShieldCheck className="h-4 w-4" /> Upload and Process
                </>
              )}
            </Button>
          </div>
        </CardBody>
      </Card>
      <HowItWorks />
    </form>
    <Card className="overflow-hidden xl:sticky xl:top-24 xl:self-start">
      <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-4">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 ring-1 ring-inset ring-indigo-100">
          <Library className="h-4 w-4" />
        </span>
        <div>
          <h3 className="text-[15px] font-semibold">Scenario library</h3>
          <p className="text-[12.5px] text-slate-500">Real PDFs through the real pipeline — one click to run.</p>
        </div>
      </div>
      <ScenarioLibrary
        disabled={uploading}
        onLoad={(sampleFile, meta) => choose(sampleFile, meta)}
        onRun={async (sampleFile, meta) => {
          choose(sampleFile, meta);
          await send(sampleFile);
        }}
      />
    </Card>
    </div>
  );
}

const STEPS = [
  { title: "Read", body: "Text layer or OCR, then AI extracts fields into a strict schema." },
  { title: "Verify", body: "24 deterministic controls: vendor, bank, GST, PO, duplicates, maths, authority." },
  { title: "Decide", body: "Approve, route to a reviewer, or reject — with every reason shown." },
];

function HowItWorks() {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {STEPS.map((step, index) => (
        <div key={step.title} className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-navy-900 text-[11px] font-semibold text-white">
              {index + 1}
            </span>
            <span className="text-[13.5px] font-semibold">{step.title}</span>
          </div>
          <p className="mt-2 text-[12.5px] leading-relaxed text-slate-500">{step.body}</p>
        </div>
      ))}
    </div>
  );
}

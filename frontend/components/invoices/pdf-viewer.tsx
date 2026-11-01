"use client";

import { ChevronLeft, ChevronRight, ExternalLink, Sparkles, ZoomIn, ZoomOut, Loader2, AlertCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { documentUrl } from "@/lib/api";
import type { FieldEvidence, VisualEvidence } from "@/types/api";

const ZOOM_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];

interface PdfViewerProps {
  invoiceId: string;
  pageCount: number | null;
  visualEvidence?: VisualEvidence | null;
  activeEvidence?: FieldEvidence | null;
  activeFieldLabel?: string | null;
  onClearEvidence?: () => void;
}

interface FlattenedEvidence {
  key: string;
  label: string;
  evidence: FieldEvidence;
}

export function PdfViewer({
  invoiceId,
  pageCount,
  visualEvidence,
  activeEvidence,
  activeFieldLabel,
  onClearEvidence,
}: PdfViewerProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(pageCount ?? 1);
  const [zoomIndex, setZoomIndex] = useState(2); // default 1.0 (100%)
  const [showEvidence, setShowEvidence] = useState(false); // Checkbox unchecked by default
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pdfDoc, setPdfDoc] = useState<any>(null);
  const [pageDimensions, setPageDimensions] = useState<Record<number, { width: number; height: number }>>({});

  const containerRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const canvasRefs = useRef<Record<number, HTMLCanvasElement | null>>({});
  const renderTasksRef = useRef<Record<number, any>>({});

  // Flatten all evidence items across visualEvidence for global rendering
  const allEvidenceItems: FlattenedEvidence[] = [];
  if (visualEvidence && typeof visualEvidence === "object") {
    for (const [key, val] of Object.entries(visualEvidence)) {
      if (!val) continue;
      if (key === "line_items" && Array.isArray(val)) {
        val.forEach((item, idx) => {
          if (item && typeof item === "object") {
            for (const [subKey, subVal] of Object.entries(item)) {
              if (
                subVal &&
                typeof subVal === "object" &&
                "norm_bbox" in subVal &&
                (subVal as FieldEvidence).norm_bbox &&
                (subVal as FieldEvidence).evidence_status !== "NOT_FOUND"
              ) {
                allEvidenceItems.push({
                  key: `line_${idx}_${subKey}`,
                  label: `Line ${idx + 1} ${subKey}`,
                  evidence: subVal as FieldEvidence,
                });
              }
            }
          }
        });
      } else if (
        typeof val === "object" &&
        "norm_bbox" in val &&
        (val as FieldEvidence).norm_bbox &&
        (val as FieldEvidence).evidence_status !== "NOT_FOUND"
      ) {
        allEvidenceItems.push({
          key,
          label: key.replace(/_/g, " "),
          evidence: val as FieldEvidence,
        });
      }
    }
  }

  // Load PDF with PDF.js
  useEffect(() => {
    let cancelled = false;

    async function loadPdf() {
      try {
        setLoading(true);
        setLoadError(null);
        // Dynamically import pdfjs-dist in the browser
        const pdfjs = await import("pdfjs-dist/build/pdf.mjs");
        if (!pdfjs.GlobalWorkerOptions.workerSrc) {
          pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
        }

        const url = documentUrl(invoiceId);
        const loadingTask = pdfjs.getDocument(url);
        const doc = await loadingTask.promise;
        if (cancelled) return;

        setPdfDoc(doc);
        setTotalPages(doc.numPages);
        setLoading(false);
      } catch (err: any) {
        console.error("Failed to load PDF via pdfjs-dist:", err);
        if (!cancelled) {
          setLoadError(err?.message || "Failed to load PDF document");
          setLoading(false);
        }
      }
    }

    loadPdf();

    return () => {
      cancelled = true;
    };
  }, [invoiceId]);

  // When activeEvidence changes, auto-scroll to the page and open/ensure page is visible
  useEffect(() => {
    if (activeEvidence && activeEvidence.page) {
      setCurrentPage(activeEvidence.page);
      const pageEl = pageRefs.current[activeEvidence.page];
      if (pageEl) {
        pageEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }
  }, [activeEvidence]);

  const scale = ZOOM_STEPS[zoomIndex];

  // Render pages onto canvases whenever pdfDoc or scale changes
  useEffect(() => {
    if (!pdfDoc) return;
    let cancelled = false;

    // Cancel any active render tasks before starting new renders
    for (const pno in renderTasksRef.current) {
      if (renderTasksRef.current[pno]) {
        try {
          renderTasksRef.current[pno].cancel();
        } catch {
          // ignore
        }
      }
    }
    renderTasksRef.current = {};

    async function renderAllPages() {
      const dims: Record<number, { width: number; height: number }> = {};

      for (let pno = 1; pno <= pdfDoc.numPages; pno++) {
        if (cancelled) break;
        try {
          const page = await pdfDoc.getPage(pno);
          const viewport = page.getViewport({ scale });
          dims[pno] = { width: viewport.width, height: viewport.height };

          const canvas = canvasRefs.current[pno];
          if (canvas) {
            const context = canvas.getContext("2d");
            if (context) {
              const outputScale = window.devicePixelRatio || 1;
              canvas.width = Math.floor(viewport.width * outputScale);
              canvas.height = Math.floor(viewport.height * outputScale);
              canvas.style.width = `${Math.floor(viewport.width)}px`;
              canvas.style.height = `${Math.floor(viewport.height)}px`;

              const transform = outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : undefined;
              const renderTask = page.render({
                canvasContext: context,
                viewport,
                transform,
              });
              renderTasksRef.current[pno] = renderTask;
              await renderTask.promise;
            }
          }
        } catch (err: any) {
          if (err?.name !== "RenderingCancelledException") {
            console.error(`Error rendering page ${pno}:`, err);
          }
        }
      }

      if (!cancelled) {
        setPageDimensions(dims);
      }
    }

    renderAllPages();

    return () => {
      cancelled = true;
      for (const pno in renderTasksRef.current) {
        if (renderTasksRef.current[pno]) {
          try {
            renderTasksRef.current[pno].cancel();
          } catch {
            // ignore
          }
        }
      }
      renderTasksRef.current = {};
    };
  }, [pdfDoc, scale]);

  const zoomPercent = Math.round(scale * 100);
  const pageItems = Array.from({ length: totalPages }, (_, i) => i + 1);

  return (
    <div className="flex h-full min-h-[580px] flex-col overflow-hidden rounded-lg border bg-white shadow-card">
      {/* Top Controls Toolbar */}
      <div className="flex items-center justify-between gap-2 border-b bg-slate-50 px-3 py-2">
        {/* Left: Show Evidence Checkbox */}
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 cursor-pointer select-none text-[13px] font-medium text-slate-700 hover:text-slate-900">
            <input
              type="checkbox"
              id="show-evidence-toggle"
              checked={showEvidence}
              onChange={(e) => setShowEvidence(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            <span>Show evidence</span>
          </label>
        </div>

        {/* Center: Page Navigation */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Previous page"
            disabled={currentPage <= 1}
            onClick={() => {
              const target = Math.max(1, currentPage - 1);
              setCurrentPage(target);
              pageRefs.current[target]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="tabular min-w-[72px] text-center text-[13px] font-medium text-slate-700">
            Page {currentPage} / {totalPages}
          </span>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Next page"
            disabled={currentPage >= totalPages}
            onClick={() => {
              const target = Math.min(totalPages, currentPage + 1);
              setCurrentPage(target);
              pageRefs.current[target]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

        {/* Right: Zoom Controls & Open Tab */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Zoom out"
            disabled={zoomIndex === 0}
            onClick={() => setZoomIndex((z) => Math.max(0, z - 1))}
          >
            <ZoomOut className="h-4 w-4" />
          </Button>
          <span className="tabular w-12 text-center text-[13px] font-medium text-slate-700">
            {zoomPercent}%
          </span>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Zoom in"
            disabled={zoomIndex === ZOOM_STEPS.length - 1}
            onClick={() => setZoomIndex((z) => Math.min(ZOOM_STEPS.length - 1, z + 1))}
          >
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button asChild variant="ghost" size="icon" aria-label="Open PDF in new tab">
            <a href={documentUrl(invoiceId)} target="_blank" rel="noreferrer">
              <ExternalLink className="h-4 w-4" />
            </a>
          </Button>
        </div>
      </div>

      {/* Active Field Banner (if user clicked 'View evidence' on a specific field) */}
      {activeEvidence && (
        <div
          className={`flex items-center justify-between border-b px-3.5 py-1.5 text-xs transition-colors ${
            activeEvidence.evidence_status === "VERIFIED"
              ? "border-blue-200 bg-blue-50/90 text-blue-900"
              : activeEvidence.evidence_status === "AMBIGUOUS"
              ? "border-amber-200 bg-amber-50/90 text-amber-900"
              : "border-slate-200 bg-slate-50 text-slate-700"
          }`}
        >
          <div className="flex items-center gap-2 overflow-hidden text-ellipsis whitespace-nowrap">
            <Sparkles className="h-3.5 w-3.5 shrink-0 text-blue-600" />
            <span className="font-semibold">{activeFieldLabel ?? "Field Evidence"}:</span>
            {activeEvidence.text ? (
              <span className="rounded bg-white/80 px-1.5 py-0.5 font-mono text-[11px] shadow-2xs">
                &ldquo;{activeEvidence.text}&rdquo;
              </span>
            ) : null}
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-medium tracking-wide ${
                activeEvidence.source === "tesseract"
                  ? "bg-purple-100 text-purple-700"
                  : "bg-emerald-100 text-emerald-700"
              }`}
            >
              {activeEvidence.source === "tesseract" ? "OCR Verified" : "PDF Text Verified"}
            </span>
            {activeEvidence.evidence_status === "AMBIGUOUS" && (
              <span className="text-[11px] text-amber-700 italic">(Multiple matches found)</span>
            )}
            {activeEvidence.evidence_status === "NOT_FOUND" && (
              <span className="text-[11px] text-rose-600 italic">(Coordinates not found on page)</span>
            )}
          </div>
          {onClearEvidence && (
            <button
              onClick={onClearEvidence}
              className="ml-2 shrink-0 font-medium text-slate-500 hover:text-slate-800"
            >
              Clear
            </button>
          )}
        </div>
      )}

      {/* Scrollable PDF Document Canvas Container */}
      <div
        ref={containerRef}
        className="relative min-h-0 w-full flex-1 overflow-auto bg-slate-200/80 p-4"
      >
        {loading && (
          <div className="flex h-full min-h-[300px] flex-col items-center justify-center gap-2 text-slate-500">
            <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            <span className="text-sm font-medium">Loading document pages...</span>
          </div>
        )}

        {loadError && (
          <div className="flex h-full min-h-[300px] flex-col items-center justify-center gap-2 text-rose-600">
            <AlertCircle className="h-6 w-6" />
            <span className="text-sm font-semibold">{loadError}</span>
          </div>
        )}

        <div className="flex flex-col items-center gap-4">
          {pageItems.map((pno) => {
            const dim = pageDimensions[pno] || { width: 595 * scale, height: 842 * scale };

            // Evidence items on this specific page
            const pageEvidence = showEvidence
              ? allEvidenceItems.filter((item) => item.evidence.page === pno && item.evidence.norm_bbox)
              : [];

            // Specific active field evidence on this page
            const activeOnThisPage =
              activeEvidence &&
              activeEvidence.page === pno &&
              activeEvidence.norm_bbox &&
              activeEvidence.evidence_status !== "NOT_FOUND";

            return (
              <div
                key={pno}
                ref={(el) => {
                  pageRefs.current[pno] = el;
                }}
                className="relative bg-white shadow-md ring-1 ring-slate-900/5 transition-all"
                style={{
                  width: `${dim.width}px`,
                  height: `${dim.height}px`,
                }}
              >
                {/* PDF Page Canvas */}
                <canvas
                  ref={(el) => {
                    canvasRefs.current[pno] = el;
                  }}
                  className="block h-full w-full bg-transparent"
                />

                {/* Evidence Overlay Layer — transparent, pointer-events-none */}
                {(showEvidence || activeOnThisPage) && (
                  <div className="absolute inset-0 pointer-events-none bg-transparent">
                    {/* Render all global evidence if Show evidence is checked */}
                    {pageEvidence.map((item, idx) => {
                      const nb = item.evidence.norm_bbox!;
                      const isAmbiguous = item.evidence.evidence_status === "AMBIGUOUS";
                      const isFocus =
                        activeEvidence &&
                        activeEvidence.norm_bbox &&
                        Math.abs(activeEvidence.norm_bbox[0] - nb[0]) < 0.001 &&
                        Math.abs(activeEvidence.norm_bbox[1] - nb[1]) < 0.001;

                      return (
                        <div
                          key={`${item.key}-${idx}`}
                          style={{
                            position: "absolute",
                            left: `${nb[0] * 100}%`,
                            top: `${nb[1] * 100}%`,
                            width: `${Math.max(0.5, (nb[2] - nb[0]) * 100)}%`,
                            height: `${Math.max(0.5, (nb[3] - nb[1]) * 100)}%`,
                          }}
                          className={`rounded transition-all ${
                            isFocus
                              ? "border-2 border-blue-600 bg-blue-500/20 ring-4 ring-blue-400/50 z-20"
                              : isAmbiguous
                              ? "border-2 border-dashed border-amber-500 bg-amber-500/15 z-10"
                              : "border-2 border-blue-600 bg-blue-500/15 z-10"
                          }`}
                          title={`${item.label} (${item.evidence.evidence_status})`}
                        />
                      );
                    })}

                    {/* If showEvidence is OFF but user clicked 'View evidence' on a field */}
                    {!showEvidence && activeOnThisPage && (
                      <div
                        style={{
                          position: "absolute",
                          left: `${activeEvidence.norm_bbox![0] * 100}%`,
                          top: `${activeEvidence.norm_bbox![1] * 100}%`,
                          width: `${Math.max(0.5, (activeEvidence.norm_bbox![2] - activeEvidence.norm_bbox![0]) * 100)}%`,
                          height: `${Math.max(0.5, (activeEvidence.norm_bbox![3] - activeEvidence.norm_bbox![1]) * 100)}%`,
                        }}
                        className={`rounded transition-all z-20 ${
                          activeEvidence.evidence_status === "AMBIGUOUS"
                            ? "border-2 border-dashed border-amber-500 bg-amber-500/25 ring-4 ring-amber-400/50"
                            : "border-2 border-blue-600 bg-blue-500/25 ring-4 ring-blue-400/50"
                        }`}
                      >
                        <div className="absolute -top-6 left-0 whitespace-nowrap rounded bg-slate-900 px-1.5 py-0.5 text-[10px] font-medium text-white shadow-md">
                          {activeFieldLabel ?? "Evidence"}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

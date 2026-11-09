"use client";

import { AlertCircle, ChevronLeft, ChevronRight, ExternalLink, Eye, Loader2, ScanSearch, X, ZoomIn, ZoomOut } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";

import { Button } from "@/components/ui/button";
import { documentUrl } from "@/lib/api";
import { allEvidence, type EvidenceItem } from "@/lib/evidence";
import { cn } from "@/lib/utils";
import type { FieldEvidence, VisualEvidence } from "@/types/api";

const ZOOM_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];
const PAD = 3; // px of breathing room around highlighted text

interface PdfViewerProps {
  invoiceId: string;
  pageCount: number | null;
  visualEvidence?: VisualEvidence | null;
  /** Values to highlight right now (one field, a line, or everything a check looked at). */
  active?: EvidenceItem[];
  onSelect?: (items: EvidenceItem[]) => void;
  onClear?: () => void;
}

function boxStyle(ev: FieldEvidence): CSSProperties {
  const [x0, y0, x1, y1] = ev.norm_bbox!;
  return {
    left: `calc(${x0 * 100}% - ${PAD}px)`,
    top: `calc(${y0 * 100}% - ${PAD}px)`,
    width: `calc(${Math.max(0.4, (x1 - x0) * 100)}% + ${PAD * 2}px)`,
    height: `calc(${Math.max(0.4, (y1 - y0) * 100)}% + ${PAD * 2}px)`,
  };
}

export function PdfViewer({ invoiceId, pageCount, visualEvidence, active = [], onSelect, onClear }: PdfViewerProps) {
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(pageCount ?? 1);
  const [zoomIndex, setZoomIndex] = useState(2);
  const [showAll, setShowAll] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [pdfDoc, setPdfDoc] = useState<any>(null);
  const [pageDimensions, setPageDimensions] = useState<Record<number, { width: number; height: number }>>({});

  const containerRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const canvasRefs = useRef<Record<number, HTMLCanvasElement | null>>({});
  const renderTasksRef = useRef<Record<number, any>>({});

  const everything = useMemo(() => allEvidence(visualEvidence), [visualEvidence]);
  const activeKeys = new Set(active.map((a) => a.key));
  const scale = ZOOM_STEPS[zoomIndex];

  // Load the PDF with PDF.js
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        setLoadError(null);
        const pdfjs = await import("pdfjs-dist/build/pdf.mjs");
        if (!pdfjs.GlobalWorkerOptions.workerSrc) pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
        const doc = await pdfjs.getDocument(documentUrl(invoiceId)).promise;
        if (cancelled) return;
        setPdfDoc(doc);
        setTotalPages(doc.numPages);
        setLoading(false);
      } catch (err) {
        if (!cancelled) {
          setLoadError((err as Error)?.message || "Failed to load PDF document");
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [invoiceId]);

  // Render every page at the current zoom
  useEffect(() => {
    if (!pdfDoc) return;
    let cancelled = false;
    const cancelAll = () => {
      for (const pno in renderTasksRef.current) {
        try {
          renderTasksRef.current[pno]?.cancel();
        } catch {
          /* ignore */
        }
      }
      renderTasksRef.current = {};
    };
    cancelAll();
    (async () => {
      const dims: Record<number, { width: number; height: number }> = {};
      for (let pno = 1; pno <= pdfDoc.numPages; pno++) {
        if (cancelled) break;
        try {
          const page = await pdfDoc.getPage(pno);
          const viewport = page.getViewport({ scale });
          dims[pno] = { width: viewport.width, height: viewport.height };
          const canvas = canvasRefs.current[pno];
          const context = canvas?.getContext("2d");
          if (canvas && context) {
            const ratio = window.devicePixelRatio || 1;
            canvas.width = Math.floor(viewport.width * ratio);
            canvas.height = Math.floor(viewport.height * ratio);
            canvas.style.width = `${Math.floor(viewport.width)}px`;
            canvas.style.height = `${Math.floor(viewport.height)}px`;
            const task = page.render({ canvasContext: context, viewport, transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : undefined });
            renderTasksRef.current[pno] = task;
            await task.promise;
          }
        } catch (err) {
          if ((err as Error)?.name !== "RenderingCancelledException") console.error(`Error rendering page ${pno}:`, err);
        }
      }
      if (!cancelled) setPageDimensions(dims);
    })();
    return () => {
      cancelled = true;
      cancelAll();
    };
  }, [pdfDoc, scale]);

  // Bring the first highlighted value into the middle of the viewer.
  const focus = active[0]?.evidence;
  useEffect(() => {
    if (!focus?.norm_bbox) return;
    const pageEl = pageRefs.current[focus.page];
    const container = containerRef.current;
    if (!pageEl || !container) return;
    setCurrentPage(focus.page);
    const [x0, y0, x1, y1] = focus.norm_bbox;
    const top = pageEl.offsetTop + ((y0 + y1) / 2) * pageEl.offsetHeight - container.clientHeight * 0.4;
    const left = pageEl.offsetLeft + ((x0 + x1) / 2) * pageEl.offsetWidth - container.clientWidth / 2;
    container.scrollTo?.({ top: Math.max(0, top), left: Math.max(0, left), behavior: "smooth" });
  }, [focus, pageDimensions]);

  const jumpTo = (target: number) => {
    setCurrentPage(target);
    pageRefs.current[target]?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const status = (ev: FieldEvidence) =>
    ev.evidence_status === "AMBIGUOUS"
      ? `best of ${ev.match_count ?? "several"} places`
      : ev.source === "tesseract"
        ? "read by OCR"
        : "exact match";

  return (
    <div className="flex h-full min-h-[580px] flex-col overflow-hidden rounded-xl border bg-white shadow-card">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-2 border-b bg-slate-50 px-3 py-2">
        <button
          type="button"
          onClick={() => setShowAll((v) => !v)}
          aria-pressed={showAll}
          disabled={everything.length === 0}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[12.5px] font-medium transition-colors disabled:opacity-40",
            showAll ? "bg-indigo-600 text-white" : "text-slate-700 ring-1 ring-inset ring-slate-200 hover:bg-white",
          )}
          title="Outline every extracted value on the document; click a box to select it"
        >
          <ScanSearch className="h-3.5 w-3.5" /> {showAll ? "Showing all fields" : "Show all fields"}
        </button>

        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" aria-label="Previous page" disabled={currentPage <= 1} onClick={() => jumpTo(Math.max(1, currentPage - 1))}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="tabular min-w-[72px] text-center text-[13px] font-medium text-slate-700">
            Page {currentPage} / {totalPages}
          </span>
          <Button variant="ghost" size="icon" aria-label="Next page" disabled={currentPage >= totalPages} onClick={() => jumpTo(Math.min(totalPages, currentPage + 1))}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" aria-label="Zoom out" disabled={zoomIndex === 0} onClick={() => setZoomIndex((z) => Math.max(0, z - 1))}>
            <ZoomOut className="h-4 w-4" />
          </Button>
          <span className="tabular w-12 text-center text-[13px] font-medium text-slate-700">{Math.round(scale * 100)}%</span>
          <Button variant="ghost" size="icon" aria-label="Zoom in" disabled={zoomIndex === ZOOM_STEPS.length - 1} onClick={() => setZoomIndex((z) => Math.min(ZOOM_STEPS.length - 1, z + 1))}>
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button asChild variant="ghost" size="icon" aria-label="Open PDF in new tab">
            <a href={documentUrl(invoiceId)} target="_blank" rel="noreferrer">
              <ExternalLink className="h-4 w-4" />
            </a>
          </Button>
        </div>
      </div>

      {/* What is highlighted */}
      {active.length > 0 && (
        <div className="flex items-start justify-between gap-2 border-b border-indigo-100 bg-indigo-50/80 px-3.5 py-2" role="status" aria-live="polite">
          <div className="flex min-w-0 flex-wrap items-center gap-1.5">
            <Eye className="h-3.5 w-3.5 shrink-0 text-indigo-600" />
            {active.map((item) => (
              <span key={item.key} className="inline-flex max-w-full items-center gap-1.5 rounded-md bg-white px-2 py-0.5 text-[11.5px] shadow-sm ring-1 ring-inset ring-indigo-100">
                <span className="font-semibold text-slate-800">{item.label}</span>
                {item.evidence.text && <span className="truncate font-mono text-[11px] text-slate-600">“{item.evidence.text}”</span>}
                <span className={cn("shrink-0 text-[10.5px]", item.evidence.evidence_status === "AMBIGUOUS" ? "text-amber-700" : "text-emerald-700")}>
                  · {status(item.evidence)}
                </span>
              </span>
            ))}
          </div>
          {onClear && (
            <button type="button" onClick={onClear} aria-label="Clear highlight" className="shrink-0 rounded p-0.5 text-slate-500 hover:bg-white hover:text-slate-800">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      )}

      {/* Pages */}
      <div ref={containerRef} className="relative min-h-0 w-full flex-1 overflow-auto bg-slate-200/80 p-4">
        {loading && (
          <div className="flex h-full min-h-[300px] flex-col items-center justify-center gap-2 text-slate-500">
            <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
            <span className="text-sm font-medium">Loading document…</span>
          </div>
        )}
        {loadError && (
          <div className="flex h-full min-h-[300px] flex-col items-center justify-center gap-2 text-rose-600">
            <AlertCircle className="h-6 w-6" />
            <span className="text-sm font-semibold">{loadError}</span>
          </div>
        )}

        <div className="flex flex-col items-center gap-4">
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((pno) => {
            const dim = pageDimensions[pno] || { width: 595 * scale, height: 842 * scale };
            const outlines = showAll ? everything.filter((e) => e.evidence.page === pno && !activeKeys.has(e.key)) : [];
            const highlights = active.filter((a) => a.evidence.page === pno && a.evidence.norm_bbox);
            return (
              <div
                key={pno}
                ref={(el) => {
                  pageRefs.current[pno] = el;
                }}
                className="relative bg-white shadow-md ring-1 ring-slate-900/5"
                style={{ width: `${dim.width}px`, height: `${dim.height}px` }}
              >
                <canvas
                  ref={(el) => {
                    canvasRefs.current[pno] = el;
                  }}
                  className="block h-full w-full"
                />
                <div className="pointer-events-none absolute inset-0">
                  {outlines.map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => onSelect?.([item])}
                      title={`${item.label}: ${item.evidence.text ?? ""}`}
                      aria-label={`Highlight ${item.label}`}
                      style={boxStyle(item.evidence)}
                      className="pointer-events-auto absolute rounded-[3px] border border-indigo-400/80 bg-indigo-400/10 transition-colors hover:bg-indigo-400/25"
                    />
                  ))}
                  {highlights.map((item, i) => (
                    <div key={item.key} style={boxStyle(item.evidence)} className="evidence-highlight absolute rounded-[4px]">
                      {(i === 0 || highlights.length <= 4) && (
                        <span className="absolute -top-[18px] left-0 whitespace-nowrap rounded bg-indigo-600 px-1.5 py-px text-[10px] font-semibold text-white shadow">
                          {item.label}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

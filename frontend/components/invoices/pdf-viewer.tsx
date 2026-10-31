"use client";

import { ChevronLeft, ChevronRight, ExternalLink, ZoomIn, ZoomOut } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { documentUrl } from "@/lib/api";

const ZOOM_STEPS = [50, 75, 100, 125, 150, 200];

/**
 * Uses the browser's native PDF renderer. Page and zoom are passed via the standard
 * `#page=N&zoom=Z` open-parameters, so navigation works without bundling a PDF library.
 */
export function PdfViewer({ invoiceId, pageCount }: { invoiceId: string; pageCount: number | null }) {
  const [page, setPage] = useState(1);
  const [zoomIndex, setZoomIndex] = useState(2);
  const pages = pageCount ?? 1;
  const src = `${documentUrl(invoiceId)}#page=${page}&zoom=${ZOOM_STEPS[zoomIndex]}&toolbar=0`;

  return (
    <div className="flex h-full min-h-[560px] flex-col overflow-hidden rounded-lg border bg-white shadow-card">
      <div className="flex items-center justify-between gap-2 border-b bg-slate-50 px-3 py-2">
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" aria-label="Previous page" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="tabular min-w-[72px] text-center text-[13px]">
            Page {page} / {pages}
          </span>
          <Button variant="ghost" size="icon" aria-label="Next page" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" aria-label="Zoom out" disabled={zoomIndex === 0} onClick={() => setZoomIndex((z) => z - 1)}>
            <ZoomOut className="h-4 w-4" />
          </Button>
          <span className="tabular w-10 text-center text-[13px]">{ZOOM_STEPS[zoomIndex]}%</span>
          <Button variant="ghost" size="icon" aria-label="Zoom in" disabled={zoomIndex === ZOOM_STEPS.length - 1} onClick={() => setZoomIndex((z) => z + 1)}>
            <ZoomIn className="h-4 w-4" />
          </Button>
          <Button asChild variant="ghost" size="icon" aria-label="Open PDF in new tab">
            <a href={documentUrl(invoiceId)} target="_blank" rel="noreferrer">
              <ExternalLink className="h-4 w-4" />
            </a>
          </Button>
        </div>
      </div>
      <iframe key={src} src={src} title="Original invoice PDF" className="min-h-0 w-full flex-1 bg-slate-100" />
    </div>
  );
}


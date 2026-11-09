import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { PdfViewer } from "@/components/invoices/pdf-viewer";
import { evidenceFor, fieldEvidence } from "@/lib/evidence";

// Mock pdfjs-dist module
vi.mock("pdfjs-dist/build/pdf.mjs", () => ({
  GlobalWorkerOptions: { workerSrc: "" },
  getDocument: vi.fn().mockReturnValue({
    promise: Promise.resolve({
      numPages: 2,
      getPage: vi.fn().mockResolvedValue({
        getViewport: vi.fn().mockReturnValue({ width: 600, height: 800 }),
        render: vi.fn().mockReturnValue({ promise: Promise.resolve() }),
      }),
    }),
  }),
}));

const box = (y: number, text: string, status: "VERIFIED" | "AMBIGUOUS" = "VERIFIED") => ({
  page: 1,
  bbox: [100, y, 200, y + 20] as [number, number, number, number],
  norm_bbox: [0.1, y / 800, 0.3, (y + 20) / 800] as [number, number, number, number],
  source: "pdf_text" as const,
  evidence_status: status,
  text,
});

const sampleEvidence = {
  invoice_number: box(100, "INV-1001"),
  subtotal: box(300, "97,000.00"),
  tax_amount: box(330, "17,460.00", "AMBIGUOUS"),
  total_amount: box(360, "1,14,460.00"),
  vendor_gstin: { ...box(0, "X"), norm_bbox: null, bbox: null, evidence_status: "NOT_FOUND" as const },
};

describe("PdfViewer click-to-highlight evidence", () => {
  it("outlines every located value only after 'Show all fields', and selects a box on click", () => {
    const onSelect = vi.fn();
    render(<PdfViewer invoiceId="inv-123" pageCount={2} visualEvidence={sampleEvidence} onSelect={onSelect} />);

    expect(screen.queryAllByRole("button", { name: /^Highlight / })).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: /show all fields/i }));

    // 4 located values; the NOT_FOUND GSTIN is never drawn.
    const outlines = screen.getAllByRole("button", { name: /^Highlight / });
    expect(outlines).toHaveLength(4);
    fireEvent.click(screen.getByRole("button", { name: "Highlight Invoice number" }));
    expect(onSelect).toHaveBeenCalledWith([expect.objectContaining({ key: "invoice_number" })]);
  });

  it("highlights the active values with a label and explains each one", () => {
    const onClear = vi.fn();
    const active = evidenceFor(sampleEvidence, "TOTAL_ARITHMETIC");
    const { container } = render(
      <PdfViewer invoiceId="inv-123" pageCount={2} visualEvidence={sampleEvidence} active={active} onClear={onClear} />,
    );

    expect(active.map((a) => a.key)).toEqual(["subtotal", "tax_amount", "total_amount"]);
    expect(container.querySelectorAll(".evidence-highlight")).toHaveLength(3);
    const banner = screen.getByRole("status");
    expect(banner).toHaveTextContent("Invoice total");
    expect(banner).toHaveTextContent("1,14,460.00");
    expect(banner).toHaveTextContent("best of"); // the ambiguous GST value says so

    fireEvent.click(screen.getByRole("button", { name: /clear highlight/i }));
    expect(onClear).toHaveBeenCalled();
  });

  it("skips values that were not found on the page", () => {
    expect(fieldEvidence(sampleEvidence, "vendor_gstin")).toBeNull();
    expect(evidenceFor(sampleEvidence, "VENDOR_GSTIN")).toEqual([]);
  });
});

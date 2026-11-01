import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PdfViewer } from "@/components/invoices/pdf-viewer";

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

describe("PdfViewer with Evidence Toggle", () => {
  const sampleEvidence = {
    invoice_number: {
      page: 1,
      bbox: [100, 100, 200, 120] as [number, number, number, number],
      norm_bbox: [0.1, 0.1, 0.3, 0.15] as [number, number, number, number],
      source: "pdf_text" as const,
      evidence_status: "VERIFIED" as const,
      text: "INV-1001",
    },
    currency: {
      page: 1,
      bbox: [100, 130, 150, 150] as [number, number, number, number],
      norm_bbox: [0.1, 0.13, 0.2, 0.17] as [number, number, number, number],
      source: "pdf_text" as const,
      evidence_status: "AMBIGUOUS" as const,
      text: "USD",
    },
  };

  it("renders with 'Show evidence' checkbox unchecked by default", () => {
    render(
      <PdfViewer
        invoiceId="inv-123"
        pageCount={2}
        visualEvidence={sampleEvidence}
      />
    );

    const checkbox = screen.getByLabelText("Show evidence") as HTMLInputElement;
    expect(checkbox).toBeInTheDocument();
    expect(checkbox.checked).toBe(false);
  });

  it("toggles evidence overlay visibility when checkbox is checked/unchecked", () => {
    const { container } = render(
      <PdfViewer
        invoiceId="inv-123"
        pageCount={2}
        visualEvidence={sampleEvidence}
      />
    );

    const checkbox = screen.getByLabelText("Show evidence") as HTMLInputElement;

    // Initially unchecked, no global overlay boxes rendered
    expect(container.querySelectorAll(".border-blue-600").length).toBe(0);

    // Toggle on
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(true);

    // Now global evidence boxes appear (1 VERIFIED blue, 1 AMBIGUOUS amber)
    const verifiedBoxes = container.querySelectorAll(".border-blue-600");
    const ambiguousBoxes = container.querySelectorAll(".border-amber-500");
    expect(verifiedBoxes.length).toBe(1);
    expect(ambiguousBoxes.length).toBe(1);

    // Toggle off
    fireEvent.click(checkbox);
    expect(checkbox.checked).toBe(false);
    expect(container.querySelectorAll(".border-blue-600").length).toBe(0);
  });
});


export interface SampleInvoiceMeta {
  file: string;
  scenario: string;
  expected_outcome: "APPROVED" | "NEEDS_REVIEW" | "REJECTED" | "PROCESSING_FAILED";
  invoice_number: string | null;
  vendor: string | null;
  po_number: string | null;
  currency: string;
  total: string | null;
  layout: string;
  description: string;
}

export const SAMPLE_INVOICES: SampleInvoiceMeta[] = [
  {
    file: "01_valid_invoice.pdf",
    scenario: "Clean Matching Invoice",
    expected_outcome: "APPROVED",
    invoice_number: "ACM/2026/1042",
    vendor: "Acme Industrial Supplies Pvt Ltd",
    po_number: "PO-2026-0001",
    currency: "INR",
    total: "114460.00",
    layout: "classic",
    description: "Matches active vendor, active PO balance, and exact mathematical totals.",
  },
  {
    file: "02_valid_multi_line.pdf",
    scenario: "Multi-line Item Match",
    expected_outcome: "APPROVED",
    invoice_number: "BOS-9012",
    vendor: "Bharat Office Solutions Pvt Ltd",
    po_number: "PO-2026-0002",
    currency: "INR",
    total: "107944.00",
    layout: "modern",
    description: "Reconciles 3 separate line items against PO quantities and prices.",
  },
  {
    file: "05_exceeds_po_balance.pdf",
    scenario: "Exceeds PO Remaining Balance",
    expected_outcome: "NEEDS_REVIEW",
    invoice_number: "CL-2026-248",
    vendor: "Cobalt Logistics LLP",
    po_number: "PO-2026-0003",
    currency: "INR",
    total: "70800.00",
    layout: "classic",
    description: "Billed total exceeds remaining active balance on PO-2026-0003.",
  },
  {
    file: "06_missing_invoice_number.pdf",
    scenario: "Missing Invoice Number",
    expected_outcome: "NEEDS_REVIEW",
    invoice_number: null,
    vendor: "Deccan Print & Packaging Ltd",
    po_number: "PO-2026-0004",
    currency: "INR",
    total: "35400.00",
    layout: "modern",
    description: "Mandatory identifier missing on document; flags human exception queue.",
  },
  {
    file: "07_inactive_vendor.pdf",
    scenario: "Suspended / Inactive Vendor",
    expected_outcome: "REJECTED",
    invoice_number: "GS-7802",
    vendor: "Gamma Stationers",
    po_number: "PO-2026-0007",
    currency: "INR",
    total: "28320.00",
    layout: "compact",
    description: "Vendor is marked INACTIVE in master data; deterministic rejection.",
  },
  {
    file: "08_vendor_name_variation.pdf",
    scenario: "Fuzzy Vendor Resolution",
    expected_outcome: "NEEDS_REVIEW",
    invoice_number: "FIT-5611",
    vendor: "Falcon I.T. Hardware Private Limited",
    po_number: "PO-2026-0006",
    currency: "INR",
    total: "66080.00",
    layout: "classic",
    description: "Punctuation/legal name variation requires human confirmation.",
  },
  {
    file: "10_arithmetic_mismatch.pdf",
    scenario: "Arithmetic Discrepancy",
    expected_outcome: "NEEDS_REVIEW",
    invoice_number: "IE/26-27/0455",
    vendor: "Indus Electricals Pvt Ltd",
    po_number: "PO-2026-0009",
    currency: "INR",
    total: "58400.00",
    layout: "compact",
    description: "Printed total diverges from line items sum (58,400 vs 56,640).",
  },
  {
    file: "16_valid_usd_invoice.pdf",
    scenario: "Foreign Currency (USD)",
    expected_outcome: "APPROVED",
    invoice_number: "KCT-USD-0112",
    vendor: "Kestrel Cloud Technologies Pvt Ltd",
    po_number: "PO-2026-0011",
    currency: "USD",
    total: "3050.00",
    layout: "modern",
    description: "Matches international PO denominated in USD with 0% tax.",
  },
];


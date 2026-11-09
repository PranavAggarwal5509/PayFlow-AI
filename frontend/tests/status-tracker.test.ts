import { describe, expect, it } from "vitest";

import {
  CHECK_META,
  DECISION_META,
  PROCESSING_META,
  REVIEW_META,
  STAGE_STATUS_META,
  TRACKER_STAGES,
} from "@/lib/status";
import { buildTracker } from "@/lib/tracker";
import type { RunDetail } from "@/types/api";

describe("Status Metadata Mappings", () => {
  it("maps decisions to correct tone and human-readable label", () => {
    expect(DECISION_META.APPROVED).toEqual({ label: "Approved", tone: "success" });
    expect(DECISION_META.NEEDS_REVIEW).toEqual({ label: "Needs review", tone: "warning" });
    expect(DECISION_META.REJECTED).toEqual({ label: "Rejected", tone: "danger" });
  });

  it("maps processing run statuses to distinct tones", () => {
    expect(PROCESSING_META.PROCESSING.tone).toBe("info");
    expect(PROCESSING_META.COMPLETED.tone).toBe("neutral");
    expect(PROCESSING_META.FAILED.tone).toBe("danger");
  });

  it("maps review statuses appropriately", () => {
    expect(REVIEW_META.PENDING.label).toBe("Pending");
    expect(REVIEW_META.PENDING.tone).toBe("warning");
    expect(REVIEW_META.APPROVED.tone).toBe("success");
    expect(REVIEW_META.REJECTED.tone).toBe("danger");
  });

  it("maps validation check statuses to UI badges", () => {
    expect(CHECK_META.PASSED.tone).toBe("success");
    expect(CHECK_META.WARNING.tone).toBe("warning");
    expect(CHECK_META.FAILED.tone).toBe("danger");
    expect(CHECK_META.SKIPPED.tone).toBe("neutral");
  });
});

describe("buildTracker (SSE Tracker Utilities)", () => {
  const baseRun: RunDetail = {
    id: "run-uuid-1",
    invoice_id: "inv-uuid-1",
    invoice_number: "INV-2026-001",
    original_file_name: "invoice.pdf",
    run_number: 1,
    status: "RUNNING",
    current_stage: "DATA_VALIDATION",
    started_at: "2026-10-15T10:00:00Z",
    completed_at: null,
    duration_seconds: null,
    error_message: null,
    decision_status: null,
    can_retry: false,
    checks: [],
    decision: null,
    invoice: null,
    stages: [
      {
        stage: "UPLOAD_RECEIVED",
        status: "COMPLETED",
        message: "File stored safely",
        started_at: "2026-10-15T10:00:00Z",
        completed_at: "2026-10-15T10:00:01Z",
      },
      {
        stage: "DOCUMENT_EXTRACTION",
        status: "COMPLETED",
        message: "Extracted 4 pages",
        started_at: "2026-10-15T10:00:01Z",
        completed_at: "2026-10-15T10:00:03Z",
      },
      {
        stage: "AI_EXTRACTION",
        status: "COMPLETED",
        message: "Structured JSON parsed",
        started_at: "2026-10-15T10:00:03Z",
        completed_at: "2026-10-15T10:00:07Z",
      },
      {
        stage: "DATA_VALIDATION",
        status: "IN_PROGRESS",
        message: "Validating tax calculations",
        started_at: "2026-10-15T10:00:07Z",
        completed_at: null,
      },
    ],
  };

  it("builds the exact user-facing stages from raw run stages", () => {
    const steps = buildTracker(baseRun);
    expect(steps).toHaveLength(TRACKER_STAGES.length);

    expect(steps[0].key).toBe("UPLOAD_RECEIVED");
    expect(steps[0].status).toBe("COMPLETED");

    expect(steps[1].key).toBe("DOCUMENT_EXTRACTION");
    expect(steps[1].status).toBe("COMPLETED");

    expect(steps[2].key).toBe("AI_EXTRACTION");
    expect(steps[2].status).toBe("COMPLETED");

    expect(steps[3].key).toBe("DATA_VALIDATION");
    expect(steps[3].status).toBe("IN_PROGRESS");

    // Later steps that have not started should be WAITING
    expect(steps[4].key).toBe("VENDOR_VERIFICATION");
    expect(steps[4].status).toBe("WAITING");
    expect(steps[5].key).toBe("PO_MATCHING");
    expect(steps[5].status).toBe("WAITING");
    expect(steps[7].key).toBe("DECISION");
    expect(steps[7].status).toBe("WAITING");
  });

  it("prioritizes FAILED status if an underlying sub-stage fails", () => {
    const failedRun: RunDetail = {
      ...baseRun,
      status: "FAILED",
      stages: [
        {
          stage: "DATA_VALIDATION",
          status: "FAILED",
          message: "Arithmetic subtotal mismatch",
          started_at: "2026-10-15T10:00:07Z",
          completed_at: "2026-10-15T10:00:08Z",
        },
      ],
    };

    const steps = buildTracker(failedRun);
    const validationStep = steps.find((s) => s.key === "DATA_VALIDATION");
    expect(validationStep?.status).toBe("FAILED");
    expect(validationStep?.message).toBe("Arithmetic subtotal mismatch");
  });
});


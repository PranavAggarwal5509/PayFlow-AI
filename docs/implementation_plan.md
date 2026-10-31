# PayFlow AI — Implementation Plan

## Principles
AI understands the invoice → deterministic FastAPI services verify → decision engine explains → humans handle exceptions.

## Contracts

### Statuses
| Concept | Values |
|---|---|
| `processing_status` (invoice) | PROCESSING, COMPLETED, FAILED |
| `decision_status` (invoice) | APPROVED, NEEDS_REVIEW, REJECTED (null until decided) |
| run `status` | QUEUED, RUNNING, COMPLETED, FAILED |
| stage | UPLOAD_RECEIVED, DOCUMENT_EXTRACTION, AI_EXTRACTION, DATA_VALIDATION, VENDOR_VERIFICATION, PO_MATCHING, DUPLICATE_CHECK, FINANCIAL_VALIDATION, DECISION |
| stage event status | IN_PROGRESS, COMPLETED, FAILED, NEEDS_ATTENTION |
| validation `status` | PASSED, WARNING, FAILED, SKIPPED |
| validation `impact` | NONE, REVIEW, REJECT (what a non-passing result means to the decision engine) |

### API envelope
`{ "data": ..., "meta": {...} | null, "error": null | {"code","message","details"} }`

### n8n ↔ backend contract
1. n8n webhook receives `{invoice_id, run_id}`.
2. `POST /internal/v1/runs/{run_id}/stage {stage:"UPLOAD_RECEIVED", action:"claim"}` — atomic QUEUED→RUNNING. `accepted:false` → duplicate trigger, workflow stops.
3. Each business endpoint is a thin wrapper over `services/pipeline.py`; it records its own stage completion and persists `validation_results`.
4. Transient errors → HTTP 503 (n8n retries, no state change). Permanent errors → HTTP 422 (backend marks run FAILED). After retries are exhausted the n8n error branch calls the stage endpoint with `status:"FAILED"`.
5. Only `/internal/v1/decide` can set a decision, and only through `decision_engine`.

## Build order
A. Plan → B. Foundation (models, migration, config, Docker) → C. Backend pipeline + unit/integration tests → D. n8n workflows → E. Frontend → F. Sample data, docs, end-to-end verification.

## Design system
Light theme, navy text (`#0f172a`), blue accent (`#2563eb`), 1px slate borders, 10px radius, Inter font. Status colours: green passed/approved, amber review, red rejected/failed, grey not checked.

## Key decisions
- PO consumption is derived from `po_allocations` (ACTIVE rows) — never stored as a mutable counter, so it cannot drift. Allocation happens under a row lock (`SELECT … FOR UPDATE`) on the PO.
- Duplicate detection: earliest-uploaded wins (deterministic, idempotent under concurrency / retries).
- `WORKFLOW_MODE=n8n|inline`: `inline` runs the same pipeline functions in-process (used by tests and as a dev fallback); production path is n8n.


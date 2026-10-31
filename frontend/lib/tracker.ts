import { TRACKER_STAGES } from "@/lib/status";
import type { RunDetail, StageStatus } from "@/types/api";

export interface TrackerStep {
  key: string;
  label: string;
  status: StageStatus | "WAITING";
  message: string | null;
  startedAt: string | null;
  completedAt: string | null;
}

const PRIORITY: StageStatus[] = ["FAILED", "IN_PROGRESS", "NEEDS_ATTENTION", "COMPLETED"];

/** Collapse persisted stage events into the 8 user-facing steps. Nothing here is simulated. */
export function buildTracker(run: RunDetail): TrackerStep[] {
  return TRACKER_STAGES.map((step) => {
    const events = run.stages.filter((e) => step.backend.includes(e.stage));
    if (events.length === 0) {
      return { key: step.key, label: step.label, status: "WAITING", message: null, startedAt: null, completedAt: null };
    }
    const status = PRIORITY.find((p) => events.some((e) => e.status === p)) ?? "COMPLETED";
    const lead = events.find((e) => e.status === status) ?? events[0];
    const starts = events.map((e) => e.started_at).sort();
    const ends = events.map((e) => e.completed_at).filter((v): v is string => !!v).sort();
    return {
      key: step.key,
      label: step.label,
      status,
      message: lead.message,
      startedAt: starts[0] ?? null,
      completedAt: status === "IN_PROGRESS" ? null : (ends[ends.length - 1] ?? null),
    };
  });
}


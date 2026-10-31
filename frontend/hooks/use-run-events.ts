"use client";

import { useEffect, useState } from "react";

import { runEventsUrl } from "@/lib/api";
import { runService } from "@/services";
import type { RunDetail } from "@/types/api";

/**
 * Live run state over Server-Sent Events. The payloads are the real persisted run state; if the
 * stream drops we fall back to polling the REST endpoint — never to a simulated timer.
 */
export function useRunEvents(runId: string): {
  run: RunDetail | null;
  error: string | null;
  refresh: () => void;
} {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let closed = false;
    let source: EventSource | null = null;
    let poll: ReturnType<typeof setInterval> | null = null;

    const startPolling = () => {
      if (poll) return;
      poll = setInterval(async () => {
        try {
          const latest = await runService.get(runId);
          if (closed) return;
          setRun(latest);
          if (latest.status === "COMPLETED" || latest.status === "FAILED") {
            if (poll) clearInterval(poll);
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : "Lost connection to the server.");
        }
      }, 2000);
    };

    runService
      .get(runId)
      .then((initial) => {
        if (closed) return;
        setRun(initial);
        if (initial.status === "COMPLETED" || initial.status === "FAILED") return;
        source = new EventSource(runEventsUrl(runId));
        source.addEventListener("run", (event) => {
          setError(null);
          setRun(JSON.parse((event as MessageEvent<string>).data) as RunDetail);
        });
        source.addEventListener("done", () => source?.close());
        source.onerror = () => {
          source?.close();
          startPolling();
        };
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Could not load run."));

    return () => {
      closed = true;
      source?.close();
      if (poll) clearInterval(poll);
    };
  }, [runId, tick]);

  return { run, error, refresh: () => setTick((value) => value + 1) };
}


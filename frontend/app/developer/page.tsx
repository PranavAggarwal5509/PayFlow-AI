"use client";

import { RefreshCw, Terminal } from "lucide-react";
import { useState } from "react";

import { OperationalMetricsSection } from "@/components/dashboard/operational-metrics";
import { Button } from "@/components/ui/button";
import { useAsync } from "@/hooks/use-async";
import { dashboardService } from "@/services";

export default function DeveloperPage() {
  const [selectedDays, setSelectedDays] = useState(30);
  const metrics = useAsync(() => dashboardService.developerAnalytics(selectedDays), [selectedDays]);
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    await metrics.reload();
    setRefreshing(false);
  };

  return (
    <div className="space-y-6">
      {/* Top Header Banner */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Developer & System Observability</h1>
            <span className="inline-flex items-center gap-1 rounded-full bg-slate-900 px-2.5 py-0.5 text-[11px] font-medium text-white shadow-2xs">
              <Terminal className="h-3 w-3 text-emerald-400" />
              Engineering Console
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Internal telemetry, LLM provider performance, pipeline stage profiling, and execution reliability.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing || metrics.loading}
            className="border-slate-200 bg-white shadow-xs hover:bg-slate-50"
          >
            <RefreshCw className={`mr-1.5 h-3.5 w-3.5 text-slate-500 ${refreshing ? "animate-spin" : ""}`} />
            Refresh Telemetry
          </Button>
        </div>
      </div>

      {metrics.error && (
        <div role="alert" className="flex items-center justify-between rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 text-sm text-red-800 shadow-xs">
          <span>Failed to load telemetry: {metrics.error}</span>
          <button className="font-semibold underline hover:text-red-900" onClick={metrics.reload}>
            Retry
          </button>
        </div>
      )}

      {metrics.loading && !metrics.data ? (
        <div className="rounded-xl border border-slate-200 bg-white p-12 text-center text-slate-500 shadow-xs">
          <RefreshCw className="mx-auto h-6 w-6 animate-spin text-slate-400" />
          <p className="mt-2 text-sm font-medium">Aggregating telemetry logs...</p>
        </div>
      ) : (
        <OperationalMetricsSection
          metrics={metrics.data ?? undefined}
          selectedDays={selectedDays}
          onSelectDays={setSelectedDays}
        />
      )}
    </div>
  );
}

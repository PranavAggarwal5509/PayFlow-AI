"use client";

import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, ChevronsUpDown } from "lucide-react";
import type { ReactNode } from "react";

import { EmptyState, ErrorState, TableSkeleton } from "@/components/tables/table-states";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { PageMeta } from "@/types/api";

interface DataTableProps<T> {
  columns: ColumnDef<T, unknown>[];
  data: T[];
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
  meta?: PageMeta;
  onPageChange?: (page: number) => void;
  /** Server-side sorting: the table reports changes, the parent refetches. */
  sorting?: SortingState;
  onSortingChange?: (sorting: SortingState) => void;
  onRowClick?: (row: T) => void;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  filtered?: boolean;
}

export function DataTable<T>({
  columns,
  data,
  loading,
  error,
  onRetry,
  meta,
  onPageChange,
  sorting = [],
  onSortingChange,
  onRowClick,
  emptyTitle = "Nothing here yet",
  emptyDescription,
  emptyAction,
  filtered,
}: DataTableProps<T>) {
  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    manualSorting: true,
    manualPagination: true,
    enableSortingRemoval: false,
    onSortingChange: (updater) => {
      const next = typeof updater === "function" ? updater(sorting) : updater;
      onSortingChange?.(next);
    },
    getCoreRowModel: getCoreRowModel(),
  });

  if (error) return <ErrorState message={error} onRetry={onRetry} />;
  if (loading && data.length === 0) return <TableSkeleton columns={Math.min(columns.length, 6)} />;
  if (!loading && data.length === 0)
    return (
      <EmptyState
        title={filtered ? "No results match your filters" : emptyTitle}
        description={filtered ? "Try adjusting or clearing the filters." : emptyDescription}
        action={filtered ? undefined : emptyAction}
      />
    );

  return (
    <div>
      <div className={cn("overflow-x-auto transition-opacity", loading && "opacity-60")}>
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b border-slate-100 bg-slate-50/80 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id}>
                {group.headers.map((header) => {
                  const sorted = header.column.getIsSorted();
                  const sortable = header.column.getCanSort();
                  return (
                    <th
                      key={header.id}
                      scope="col"
                      aria-sort={sorted ? (sorted === "asc" ? "ascending" : "descending") : undefined}
                      className="whitespace-nowrap px-5 py-3 font-semibold"
                    >
                      {header.isPlaceholder ? null : sortable ? (
                        <button
                          type="button"
                          onClick={header.column.getToggleSortingHandler()}
                          className="inline-flex items-center gap-1 hover:text-foreground"
                        >
                          {flexRender(header.column.columnDef.header, header.getContext())}
                          {sorted === "asc" ? (
                            <ArrowUp className="h-3 w-3" />
                          ) : sorted === "desc" ? (
                            <ArrowDown className="h-3 w-3" />
                          ) : (
                            <ChevronsUpDown className="h-3 w-3 opacity-40" />
                          )}
                        </button>
                      ) : (
                        flexRender(header.column.columnDef.header, header.getContext())
                      )}
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-slate-100">
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                onClick={onRowClick ? () => onRowClick(row.original) : undefined}
                onKeyDown={
                  onRowClick
                    ? (event) => {
                        if (event.key === "Enter") onRowClick(row.original);
                      }
                    : undefined
                }
                tabIndex={onRowClick ? 0 : undefined}
                className={cn(
                  "transition-colors",
                  onRowClick && "group cursor-pointer hover:bg-indigo-50/40 focus:bg-indigo-50/40 focus:outline-none",
                )}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-5 py-3.5 align-middle">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {meta && onPageChange && <Pagination meta={meta} onPageChange={onPageChange} />}
    </div>
  );
}

function Pagination({ meta, onPageChange }: { meta: PageMeta; onPageChange: (page: number) => void }) {
  const from = meta.total === 0 ? 0 : (meta.page - 1) * meta.page_size + 1;
  const to = Math.min(meta.page * meta.page_size, meta.total);
  return (
    <div className="flex items-center justify-between border-t px-4 py-3 text-[13px] text-muted-foreground">
      <span className="tabular">
        {from}–{to} of {meta.total}
      </span>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={meta.page <= 1}
          onClick={() => onPageChange(meta.page - 1)}
          aria-label="Previous page"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <span className="tabular">
          Page {meta.page} / {meta.total_pages}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={meta.page >= meta.total_pages}
          onClick={() => onPageChange(meta.page + 1)}
          aria-label="Next page"
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}


"use client";

import type { SortingState } from "@tanstack/react-table";
import { useCallback, useState } from "react";

/** Shared list state: page, sort and filters, all translated into API query params. */
export function useListState<F extends Record<string, string>>(
  initialFilters: F,
  initialSort: SortingState,
) {
  const [filters, setFilters] = useState<F>(initialFilters);
  const [page, setPage] = useState(1);
  const [sorting, setSorting] = useState<SortingState>(initialSort);

  const setFilter = useCallback((key: keyof F, value: string) => {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  }, []);
  const clear = useCallback(() => {
    setFilters(initialFilters);
    setPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const active = Object.entries(filters).some(([key, value]) => value !== initialFilters[key]);
  const sortParams = sorting[0]
    ? { sort_by: sorting[0].id, sort_dir: sorting[0].desc ? "desc" : "asc" }
    : {};

  return { filters, setFilter, clear, active, page, setPage, sorting, setSorting, sortParams };
}


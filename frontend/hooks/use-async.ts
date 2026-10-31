"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api";

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

/** Fetches on mount and whenever `deps` change; ignores stale responses. */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const latest = useRef(0);

  useEffect(() => {
    const id = ++latest.current;
    setLoading(true);
    setError(null);
    loader()
      .then((result) => {
        if (id === latest.current) setData(result);
      })
      .catch((err: unknown) => {
        if (id === latest.current)
          setError(err instanceof ApiError ? err.message : "Something went wrong.");
      })
      .finally(() => {
        if (id === latest.current) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  return { data, loading, error, reload };
}


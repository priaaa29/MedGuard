"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useEffectEvent, useState } from "react";
import { ApiError } from "@/lib/api";

type QueryState<T> =
  | { status: "loading"; data: null; error: null }
  | { status: "success"; data: T; error: null }
  | { status: "error"; data: null; error: ApiError };

/**
 * Minimal data hook for client pages: loading / success / error, a reload
 * function, and a redirect to /login when the session has expired.
 */
export function useApiQuery<T>(load: () => Promise<T>, loginReturnTo: string) {
  const router = useRouter();
  const [state, setState] = useState<QueryState<T>>({ status: "loading", data: null, error: null });
  const [attempt, setAttempt] = useState(0);
  // Always calls the latest `load` without making the effect re-run when it changes.
  const runLoad = useEffectEvent(() => load());

  useEffect(() => {
    let cancelled = false;
    runLoad()
      .then((data) => !cancelled && setState({ status: "success", data, error: null }))
      .catch((error: unknown) => {
        if (cancelled) return;
        const apiError = error instanceof ApiError ? error : new ApiError(0, "Something went wrong. Please try again.");
        if (apiError.status === 401) {
          router.replace(`/login?next=${encodeURIComponent(loginReturnTo)}`);
          return;
        }
        setState({ status: "error", data: null, error: apiError });
      });
    return () => {
      cancelled = true;
    };
  }, [attempt, loginReturnTo, router]);

  const reload = useCallback(() => {
    setState({ status: "loading", data: null, error: null });
    setAttempt((n) => n + 1);
  }, []);

  const setData = useCallback((data: T) => setState({ status: "success", data, error: null }), []);

  return { ...state, reload, setData };
}

"use client";

import { AlertCircle, CalendarClock, ChevronRight, Plus } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useApiQuery } from "@/lib/use-api";

export function RoutineList() {
  const query = useApiQuery(api.listRoutines, "/routines");

  if (query.status === "loading") {
    return (
      <ul className="space-y-3" aria-label="Loading routines" aria-busy>
        {Array.from({ length: 3 }).map((_, index) => (
          <li key={index}>
            <Skeleton className="h-24 w-full rounded-xl" />
          </li>
        ))}
      </ul>
    );
  }

  if (query.status === "error") {
    return (
      <div role="alert" className="flex flex-col items-start gap-3 rounded-xl border border-destructive/30 bg-destructive/5 p-5">
        <p className="flex items-center gap-2 font-medium text-destructive">
          <AlertCircle className="size-4" aria-hidden />
          Couldn&apos;t load your routines
        </p>
        <p className="text-sm text-muted-foreground">{query.error.message}</p>
        <Button variant="outline" onClick={query.reload}>
          Try again
        </Button>
      </div>
    );
  }

  if (query.data.length === 0) {
    return (
      <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed border-border px-6 py-16 text-center">
        <span className="flex size-12 items-center justify-center rounded-full bg-secondary text-primary">
          <CalendarClock className="size-6" aria-hidden />
        </span>
        <div className="space-y-1">
          <p className="font-medium">No routines yet</p>
          <p className="max-w-sm text-muted-foreground">
            Add a prescription and MedGuard will plan when to take each medicine.
          </p>
        </div>
        <Button asChild>
          <Link href="/routines/new">
            <Plus data-icon="inline-start" aria-hidden />
            Create your first routine
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <ul className="space-y-3">
      {query.data.map((routine) => (
        <li key={routine.id}>
          <Link
            href={`/routines/${routine.id}`}
            className="group flex items-center gap-4 rounded-xl border border-border bg-card p-5 transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="truncate font-medium">{routine.title}</p>
                {routine.status === "pending" && <Badge variant="secondary">Building…</Badge>}
                {routine.status === "failed" && <Badge variant="destructive">Couldn&apos;t build</Badge>}
                {routine.status === "ready" &&
                  (routine.valid ? (
                    <Badge variant="success">Checked</Badge>
                  ) : (
                    <Badge variant="warning">Needs pharmacist review</Badge>
                  ))}
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                <span className="tabular-nums">{routine.medicines.length}</span>{" "}
                {routine.medicines.length === 1 ? "medicine" : "medicines"}
                {routine.status === "ready" && (
                  <>
                    {" "}
                    · <span className="tabular-nums">{routine.dose_count}</span> daily{" "}
                    {routine.dose_count === 1 ? "dose" : "doses"}
                  </>
                )}{" "}
                · {formatDate(routine.created_at)}
              </p>
            </div>
            <ChevronRight
              className="size-5 shrink-0 text-muted-foreground motion-safe:transition-transform motion-safe:group-hover:translate-x-0.5"
              aria-hidden
            />
          </Link>
        </li>
      ))}
    </ul>
  );
}

"use client";

import { Check, Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

// The API doesn't stream progress, so these advance on a timer that roughly
// matches how long each stage takes. The last stage waits for the response.
const STAGES = [
  { label: "Checking food and drug interactions", after: 0 },
  { label: "Planning times around your day", after: 12_000 },
  { label: "Checking the timetable against timing rules", after: 30_000 },
];

/** `startedAt` (ISO) lets the stages pick up where they were after a reload. */
export function GeneratingStep({ startedAt }: { startedAt: string }) {
  const started = new Date(startedAt).getTime();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const elapsed = Math.max(0, now - started);

  const current = STAGES.findLastIndex((stage) => elapsed >= stage.after);

  return (
    <div className="rounded-xl border border-border bg-card px-6 py-12" role="status" aria-live="polite">
      <h2 className="text-center text-xl font-semibold">Building your routine</h2>
      <p className="mt-1 text-center text-muted-foreground">This usually takes under a minute. You can leave this page; it keeps going and is saved to My routines.</p>
      <ol className="mx-auto mt-8 max-w-sm space-y-4">
        {STAGES.map((stage, index) => {
          const done = index < current;
          const active = index === current;
          return (
            <li key={stage.label} className="flex items-center gap-3">
              <span
                className={cn(
                  "flex size-7 shrink-0 items-center justify-center rounded-full border",
                  done && "border-primary bg-primary text-primary-foreground",
                  active && "border-primary text-primary",
                  !done && !active && "border-border",
                )}
              >
                {done ? (
                  <Check className="size-3.5" aria-hidden />
                ) : active ? (
                  <Loader2 className="size-3.5 animate-spin motion-reduce:animate-none" aria-hidden />
                ) : null}
              </span>
              <span className={cn(!done && !active && "text-muted-foreground", active && "font-medium")}>
                {stage.label}
                {done && <span className="sr-only"> (done)</span>}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

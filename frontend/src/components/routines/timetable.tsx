import { Moon, Sun, Utensils } from "lucide-react";
import type { DailySchedule, ScheduledDose } from "@/lib/types";

type Row =
  | { kind: "event"; time: string; label: string; icon: typeof Sun }
  | { kind: "doses"; time: string; doses: ScheduledDose[] };

const EVENTS: { key: keyof DailySchedule; label: string; icon: typeof Sun }[] = [
  { key: "wake", label: "Wake up", icon: Sun },
  { key: "breakfast", label: "Breakfast", icon: Utensils },
  { key: "lunch", label: "Lunch", icon: Utensils },
  { key: "dinner", label: "Dinner", icon: Utensils },
  { key: "sleep", label: "Sleep", icon: Moon },
];

function buildRows(doses: ScheduledDose[], schedule: DailySchedule): Row[] {
  const byTime = new Map<string, ScheduledDose[]>();
  for (const dose of doses) byTime.set(dose.time, [...(byTime.get(dose.time) ?? []), dose]);

  const rows: Row[] = [
    ...EVENTS.map(({ key, label, icon }) => ({ kind: "event" as const, time: schedule[key], label, icon })),
    ...[...byTime].map(([time, group]) => ({ kind: "doses" as const, time, doses: group })),
  ];
  // Same minute: the meal comes first, so "with breakfast" doses sit under breakfast.
  return rows.sort((a, b) => a.time.localeCompare(b.time) || (a.kind === "event" ? -1 : 1));
}

export function Timetable({ doses, schedule }: { doses: ScheduledDose[]; schedule: DailySchedule }) {
  const rows = buildRows(doses, schedule);

  return (
    // Rail at left-21 (5.25rem) = time column w-14 + gap-4 + half of the size-6 marker.
    <ol className="relative space-y-1 before:absolute before:top-3 before:bottom-3 before:left-21 before:w-px before:bg-border">
      {rows.map((row) =>
        row.kind === "event" ? (
          <li key={`event-${row.label}`} className="relative flex items-center gap-4 py-1.5 text-sm text-muted-foreground">
            <span className="w-14 shrink-0 text-right font-mono tabular-nums">{row.time}</span>
            <span className="relative z-10 flex size-6 shrink-0 items-center justify-center rounded-full border border-border bg-background">
              <row.icon className="size-3.5" aria-hidden />
            </span>
            <span>{row.label}</span>
          </li>
        ) : (
          <li key={`dose-${row.time}`} className="relative flex gap-4 py-2">
            <span className="w-14 shrink-0 pt-3.5 text-right font-mono font-semibold tabular-nums">{row.time}</span>
            <span className="relative z-10 mt-4 size-3 shrink-0 translate-x-1.5 rounded-full bg-primary ring-4 ring-background" aria-hidden />
            <ul className="min-w-0 flex-1 space-y-2">
              {row.doses.map((dose) => (
                <li key={`${dose.medicine}-${dose.time}`} className="rounded-lg border border-border bg-card px-4 py-3">
                  <p className="font-medium">
                    {dose.medicine}
                    {dose.dose && <span className="font-normal text-muted-foreground"> · {dose.dose}</span>}
                  </p>
                  {dose.note && <p className="mt-0.5 text-sm text-muted-foreground">{dose.note}</p>}
                </li>
              ))}
            </ul>
          </li>
        ),
      )}
    </ol>
  );
}

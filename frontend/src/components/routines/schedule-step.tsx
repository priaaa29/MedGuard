"use client";

import { AlertCircle, Loader2 } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { validateSchedule } from "@/components/routines/draft";
import type { DailySchedule } from "@/lib/types";

const TIMES: { key: keyof DailySchedule; label: string }[] = [
  { key: "wake", label: "Wake up" },
  { key: "breakfast", label: "Breakfast" },
  { key: "lunch", label: "Lunch" },
  { key: "dinner", label: "Dinner" },
  { key: "sleep", label: "Go to sleep" },
];

type Props = {
  schedule: DailySchedule;
  title: string;
  submitError: string | null;
  submitting: boolean;
  onChange: (schedule: DailySchedule) => void;
  onTitleChange: (title: string) => void;
  onBack: () => void;
  onSubmit: () => void;
};

export function ScheduleStep({ schedule, title, submitError, submitting, onChange, onTitleChange, onBack, onSubmit }: Props) {
  const [error, setError] = useState<string | null>(null);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const problem = validateSchedule(schedule);
    setError(problem);
    if (problem) {
      document.getElementById("time-wake")?.focus();
      return;
    }
    onSubmit();
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Your usual day</h2>
        <p className="mt-1 text-muted-foreground">
          Medicines are planned around when you wake, eat and sleep. Rough times are fine.
        </p>
      </div>

      {submitError && (
        <Alert variant="destructive" role="alert">
          <AlertCircle aria-hidden />
          <AlertTitle>Couldn&apos;t build the routine</AlertTitle>
          <AlertDescription>{submitError} Your medicines and times are still here, so you can try again.</AlertDescription>
        </Alert>
      )}

      <fieldset className="rounded-xl border border-border bg-card p-5">
        <legend className="sr-only">Daily times</legend>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {TIMES.map(({ key, label }) => (
            <Field key={key} data-invalid={error ? true : undefined}>
              <FieldLabel htmlFor={`time-${key}`}>{label}</FieldLabel>
              <Input
                id={`time-${key}`}
                type="time"
                required
                value={schedule[key]}
                onChange={(event) => onChange({ ...schedule, [key]: event.target.value })}
                className="font-mono tabular-nums"
                aria-invalid={error ? true : undefined}
                aria-describedby={error ? "schedule-error" : undefined}
              />
            </Field>
          ))}
        </div>
        {error && (
          <FieldError id="schedule-error" className="mt-4">
            {error}
          </FieldError>
        )}
      </fieldset>

      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="routine-title">Name this routine (optional)</FieldLabel>
          <Input
            id="routine-title"
            value={title}
            maxLength={100}
            onChange={(event) => onTitleChange(event.target.value)}
            placeholder="Mum's tablets"
            autoComplete="off"
            aria-describedby="routine-title-hint"
          />
          <FieldDescription id="routine-title-hint">If you leave it blank, we&apos;ll use the medicine names.</FieldDescription>
        </Field>
      </FieldGroup>

      <div className="flex flex-col-reverse gap-3 border-t border-border pt-6 sm:flex-row sm:justify-between">
        <Button type="button" variant="ghost" onClick={onBack}>
          Back
        </Button>
        <Button type="submit" size="lg" disabled={submitting} aria-busy={submitting}>
          {submitting && <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden />}
          Build my routine
        </Button>
      </div>
    </form>
  );
}

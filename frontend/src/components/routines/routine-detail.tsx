"use client";

import { AlertCircle, AlertOctagon, ArrowLeft, CircleCheck, Loader2, Pencil, Trash2, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { toast } from "sonner";
import { InteractionList } from "@/components/routines/interaction-list";
import { Timetable } from "@/components/routines/timetable";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { formatDate, formatGap, MEAL_RELATION_LABELS, SOURCE_LABELS } from "@/lib/format";
import type { RoutineDetail as RoutineDetailType } from "@/lib/types";
import { useApiQuery } from "@/lib/use-api";

const RULE_SOURCE_LABELS = {
  prescription: "Your prescription",
  curated_rule: SOURCE_LABELS.curated_rule,
  ai: SOURCE_LABELS.ai,
  default: "",
} as const;

function Section({ title, children, id }: { title: string; id: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={id} className="space-y-4">
      <h2 id={id} className="text-xl font-semibold">
        {title}
      </h2>
      {children}
    </section>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-8" aria-busy aria-label="Loading routine">
      <Skeleton className="h-10 w-2/3" />
      <Skeleton className="h-20 w-full rounded-xl" />
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full rounded-lg" />
        ))}
      </div>
    </div>
  );
}

export function RoutineDetail() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const query = useApiQuery(() => api.getRoutine(id), `/routines/${id}`);

  if (query.status === "loading") return <DetailSkeleton />;

  if (query.status === "error") {
    const notFound = query.error.status === 404;
    return (
      <div role="alert" className="flex flex-col items-start gap-3 rounded-xl border border-border bg-card p-6">
        <p className="flex items-center gap-2 font-medium">
          <AlertCircle className="size-4 text-destructive" aria-hidden />
          {notFound ? "Routine not found" : "Couldn't load this routine"}
        </p>
        <p className="text-muted-foreground">
          {notFound ? "It may have been deleted, or the link is wrong." : query.error.message}
        </p>
        <div className="flex gap-3">
          {!notFound && (
            <Button variant="outline" onClick={query.reload}>
              Try again
            </Button>
          )}
          <Button asChild variant={notFound ? "default" : "ghost"}>
            <Link href="/routines">Back to my routines</Link>
          </Button>
        </div>
      </div>
    );
  }

  return <RoutineView routine={query.data} onRenamed={query.setData} />;
}

function RoutineView({
  routine,
  onRenamed,
}: {
  routine: RoutineDetailType;
  onRenamed: (routine: RoutineDetailType) => void;
}) {
  const { result, schedule } = routine;
  const { routine: plan } = result;
  const highRisk = result.warnings.filter((w) => w.startsWith("High-risk"));
  const otherWarnings = result.warnings.filter((w) => !w.startsWith("High-risk"));

  return (
    <div className="space-y-10">
      <div className="space-y-4">
        <Button asChild variant="ghost" className="-ml-3 text-muted-foreground">
          <Link href="/routines">
            <ArrowLeft data-icon="inline-start" aria-hidden />
            My routines
          </Link>
        </Button>
        <TitleBar routine={routine} onRenamed={onRenamed} />
      </div>

      {plan.valid ? (
        <Alert variant="success">
          <CircleCheck aria-hidden />
          <AlertTitle>Timetable checked</AlertTitle>
          <AlertDescription>
            Every time below passed MedGuard&apos;s timing checks. Show it to your pharmacist before you start.
          </AlertDescription>
        </Alert>
      ) : (
        <Alert variant="warning">
          <TriangleAlert aria-hidden />
          <AlertTitle>Needs your pharmacist</AlertTitle>
          <AlertDescription>
            <p>{plan.summary}</p>
            {plan.issues.length > 0 && (
              <ul className="mt-2 list-disc space-y-1 pl-4">
                {plan.issues.map((issue) => (
                  <li key={`${issue.code}-${issue.message}`}>{issue.message}</li>
                ))}
              </ul>
            )}
          </AlertDescription>
        </Alert>
      )}

      {highRisk.map((warning) => (
        <Alert key={warning} variant="destructive">
          <AlertOctagon aria-hidden />
          <AlertTitle>High-risk interaction</AlertTitle>
          <AlertDescription>{warning.replace(/^High-risk interaction found\.\s*/, "")}</AlertDescription>
        </Alert>
      ))}

      <Section title="Daily timetable" id="timetable-heading">
        {plan.valid && plan.summary && <p className="max-w-prose text-muted-foreground">{plan.summary}</p>}
        {plan.doses.length > 0 ? (
          <div className={plan.valid ? undefined : "opacity-70"}>
            {!plan.valid && (
              <p className="mb-3 text-sm font-medium text-warning">Not verified. Don&apos;t follow these times yet.</p>
            )}
            <Timetable doses={plan.doses} schedule={schedule} />
          </div>
        ) : (
          <p className="text-muted-foreground">There are no daily medicines to schedule.</p>
        )}
        {plan.as_needed.length > 0 && (
          <div className="rounded-lg border border-border bg-card px-4 py-3">
            <p className="font-medium">Only when needed</p>
            <p className="mt-1 text-sm text-muted-foreground">
              {plan.as_needed.join(", ")}. Follow the instructions on your prescription for these.
            </p>
          </div>
        )}
        {otherWarnings.length > 0 && (
          <ul className="space-y-2 text-sm text-muted-foreground">
            {otherWarnings.map((warning) => (
              <li key={warning} className="flex gap-2">
                <TriangleAlert className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
                {warning}
              </li>
            ))}
          </ul>
        )}
      </Section>

      {plan.food_guidance.length > 0 && (
        <Section title="Food and drink" id="food-heading">
          <ul className="space-y-2">
            {plan.food_guidance.map((line) => (
              <li key={line} className="flex gap-3">
                <span className="mt-2.5 size-1.5 shrink-0 rounded-full bg-primary" aria-hidden />
                <span className="max-w-prose">{line}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Interactions" id="interactions-heading">
        <InteractionList findings={result.interactions} />
      </Section>

      <Section title="Timing rules used" id="rules-heading">
        <p className="max-w-prose text-muted-foreground">
          These are the rules the timetable was checked against, and where each one came from.
        </p>
        <ul className="divide-y divide-border rounded-lg border border-border bg-card">
          {result.constraints.medications.map((rule) => (
            <li key={rule.medicine} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-4 py-3">
              <span className="font-medium">{rule.medicine}</span>
              <span className="text-sm text-muted-foreground">
                {MEAL_RELATION_LABELS[rule.meal_relation]}
                {rule.time_of_day !== "any" && ` · ${rule.time_of_day}`}
                {rule.min_gap_minutes > 0 && ` · doses ≥ ${formatGap(rule.min_gap_minutes)} apart`}
                {rule.meal_relation_source !== "default" && ` · ${RULE_SOURCE_LABELS[rule.meal_relation_source]}`}
              </span>
            </li>
          ))}
          {result.constraints.separations.map((sep) => (
            <li key={`${sep.medicine_a}-${sep.medicine_b}`} className="px-4 py-3">
              <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <span className="font-medium">
                  {sep.medicine_a} ↔ {sep.medicine_b}
                </span>
                <Badge variant="secondary">{SOURCE_LABELS[sep.source]}</Badge>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">{sep.reason}</p>
            </li>
          ))}
        </ul>
      </Section>

      {/* The site footer carries the medical disclaimer on every page. */}
      <p className="border-t border-border pt-6 text-sm text-muted-foreground">
        Created {formatDate(routine.created_at)}.
      </p>
    </div>
  );
}

function TitleBar({ routine, onRenamed }: { routine: RoutineDetailType; onRenamed: (r: RoutineDetailType) => void }) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(routine.title);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim()) return setError("Enter a name.");
    setSaving(true);
    try {
      const summary = await api.renameRoutine(routine.id, title.trim());
      onRenamed({ ...routine, title: summary.title, updated_at: summary.updated_at });
      setEditing(false);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't rename. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    setDeleting(true);
    try {
      await api.deleteRoutine(routine.id);
      toast.success("Routine deleted");
      router.push("/routines");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Couldn't delete. Please try again.");
      setDeleting(false);
    }
  }

  if (editing) {
    return (
      <form onSubmit={save} className="flex flex-col gap-3 sm:flex-row sm:items-end" noValidate>
        <Field className="flex-1" data-invalid={error ? true : undefined}>
          <FieldLabel htmlFor="rename">Routine name</FieldLabel>
          <Input
            id="rename"
            value={title}
            maxLength={100}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => e.key === "Escape" && setEditing(false)}
            autoFocus
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? "rename-error" : undefined}
          />
          {error && <FieldError id="rename-error">{error}</FieldError>}
        </Field>
        <div className="flex gap-2">
          <Button type="submit" disabled={saving}>
            {saving && <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden />}
            Save
          </Button>
          <Button type="button" variant="ghost" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </div>
      </form>
    );
  }

  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <h1 className="min-w-0 text-3xl font-semibold tracking-tight wrap-break-word">{routine.title}</h1>
      <div className="flex gap-2">
        <Button variant="outline" onClick={() => setEditing(true)}>
          <Pencil data-icon="inline-start" aria-hidden />
          Rename
        </Button>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="outline" size="icon" aria-label="Delete routine">
              <Trash2 aria-hidden />
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete this routine?</AlertDialogTitle>
              <AlertDialogDescription>
                &ldquo;{routine.title}&rdquo; will be permanently deleted. This can&apos;t be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Keep it</AlertDialogCancel>
              <AlertDialogAction variant="destructive" onClick={remove} disabled={deleting}>
                {deleting && <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden />}
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  );
}

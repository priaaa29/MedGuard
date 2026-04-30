"use client";

import { AlertTriangle, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { emptyDraft, validateDrafts } from "@/components/routines/draft";
import type { DraftErrors, DraftMedication } from "@/components/routines/draft";
import { MEAL_RELATION_OPTIONS } from "@/lib/format";
import type { MealRelation } from "@/lib/types";
import { cn } from "@/lib/utils";

const FREQUENCIES = [
  { value: "1", label: "Once a day" },
  { value: "2", label: "Twice a day" },
  { value: "3", label: "3 times a day" },
  { value: "4", label: "4 times a day" },
  { value: "5", label: "5 times a day" },
  { value: "6", label: "6 times a day" },
  { value: "prn", label: "Only when needed" },
];

type Props = {
  drafts: DraftMedication[];
  warnings: string[];
  onChange: (drafts: DraftMedication[]) => void;
  onBack: () => void;
  onContinue: () => void;
};

export function ReviewStep({ drafts, warnings, onChange, onBack, onContinue }: Props) {
  const [errors, setErrors] = useState<Record<string, DraftErrors>>({});
  const uncertainCount = drafts.reduce((sum, d) => sum + d.uncertain.length, 0);

  function update(key: string, patch: Partial<DraftMedication>, touched: string) {
    onChange(
      drafts.map((d) =>
        d.key === key ? { ...d, ...patch, uncertain: d.uncertain.filter((field) => field !== touched) } : d,
      ),
    );
    if (errors[key]) {
      const rest = { ...errors[key] };
      delete rest[touched as keyof DraftErrors];
      setErrors({ ...errors, [key]: rest });
    }
  }

  function add() {
    const draft = emptyDraft();
    onChange([...drafts, draft]);
    // Focus the new row's name field once it renders.
    requestAnimationFrame(() => document.getElementById(`${draft.key}-name`)?.focus());
  }

  function remove(key: string) {
    onChange(drafts.filter((d) => d.key !== key));
  }

  function submit() {
    const found = validateDrafts(drafts);
    setErrors(found);
    const firstKey = drafts.find((d) => found[d.key])?.key;
    if (firstKey) {
      const field = found[firstKey].name ? "name" : "frequency";
      document.getElementById(`${firstKey}-${field}`)?.focus();
      return;
    }
    onContinue();
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Check your medicines</h2>
        <p className="mt-1 text-muted-foreground">
          Make sure each one matches your prescription. MedGuard plans times around exactly what you confirm here.
        </p>
      </div>

      {(warnings.length > 0 || uncertainCount > 0) && (
        <Alert variant="warning">
          <AlertTriangle aria-hidden />
          <AlertTitle>Some details need a second look</AlertTitle>
          <AlertDescription>
            <ul className="mt-1 list-disc space-y-1 pl-4">
              {uncertainCount > 0 && <li>Highlighted fields were hard to read. Check them against your prescription.</li>}
              {warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      <ol className="space-y-4">
        {drafts.map((draft, index) => {
          const rowErrors = errors[draft.key] ?? {};
          const flagged = (field: string) => draft.uncertain.includes(field);
          const flagClass = (field: string) => (flagged(field) ? "border-warning bg-warning/5" : undefined);
          const id = (field: string) => `${draft.key}-${field}`;
          const describe = (field: string, hasError: boolean) =>
            [hasError ? id(`${field}-error`) : null, flagged(field) ? id(`${field}-flag`) : null]
              .filter(Boolean)
              .join(" ") || undefined;
          const flagNote = (field: string) =>
            flagged(field) ? (
              <FieldDescription id={id(`${field}-flag`)} className="text-warning">
                Check this
              </FieldDescription>
            ) : null;

          return (
            <li key={draft.key} className="relative rounded-xl border border-border bg-card p-5">
              <fieldset>
                {/* legend must be the fieldset's first child to be announced as its name */}
                <legend className="mb-4 flex min-h-10 items-center gap-2 pr-12 font-medium">
                  <span className="font-mono text-sm text-muted-foreground tabular-nums">{index + 1}.</span>
                  {draft.name.trim() || "New medicine"}
                  {draft.uncertain.length > 0 && <Badge variant="warning">Check</Badge>}
                </legend>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="absolute top-5 right-5"
                  onClick={() => remove(draft.key)}
                  disabled={drafts.length === 1}
                  aria-label={`Remove ${draft.name.trim() || "this medicine"}`}
                >
                  <Trash2 aria-hidden />
                </Button>

                <div className="grid gap-4 sm:grid-cols-2">
                  <Field data-invalid={rowErrors.name ? true : undefined}>
                    <FieldLabel htmlFor={id("name")}>Medicine name</FieldLabel>
                    <Input
                      id={id("name")}
                      value={draft.name}
                      onChange={(e) => update(draft.key, { name: e.target.value }, "name")}
                      className={flagClass("name")}
                      spellCheck={false}
                      autoComplete="off"
                      aria-invalid={rowErrors.name ? true : undefined}
                      aria-describedby={describe("name", !!rowErrors.name)}
                    />
                    {flagNote("name")}
                    {rowErrors.name && <FieldError id={id("name-error")}>{rowErrors.name}</FieldError>}
                  </Field>

                  <Field>
                    <FieldLabel htmlFor={id("strength")}>Strength</FieldLabel>
                    <Input
                      id={id("strength")}
                      value={draft.strength}
                      onChange={(e) => update(draft.key, { strength: e.target.value }, "strength")}
                      placeholder="500 mg"
                      className={flagClass("strength")}
                      autoComplete="off"
                      aria-describedby={describe("strength", false)}
                    />
                    {flagNote("strength")}
                  </Field>

                  <Field>
                    <FieldLabel htmlFor={id("dose")}>Amount per dose</FieldLabel>
                    <Input
                      id={id("dose")}
                      value={draft.dose}
                      onChange={(e) => update(draft.key, { dose: e.target.value }, "dose")}
                      placeholder="1 tablet"
                      className={flagClass("dose")}
                      autoComplete="off"
                      aria-describedby={describe("dose", false)}
                    />
                    {flagNote("dose")}
                  </Field>

                  <Field data-invalid={rowErrors.frequency ? true : undefined}>
                    <FieldLabel htmlFor={id("frequency")}>How often</FieldLabel>
                    <Select
                      value={draft.frequency || undefined}
                      onValueChange={(value) => update(draft.key, { frequency: value }, "frequency")}
                    >
                      <SelectTrigger
                        id={id("frequency")}
                        className={cn("w-full", flagClass("frequency"))}
                        aria-invalid={rowErrors.frequency ? true : undefined}
                        aria-describedby={describe("frequency", !!rowErrors.frequency)}
                      >
                        <SelectValue placeholder="Choose…" />
                      </SelectTrigger>
                      <SelectContent>
                        {FREQUENCIES.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {flagNote("frequency")}
                    {rowErrors.frequency && <FieldError id={id("frequency-error")}>{rowErrors.frequency}</FieldError>}
                  </Field>

                  <Field className="sm:col-span-2">
                    <FieldLabel htmlFor={id("mealRelation")}>Food instructions</FieldLabel>
                    <Select
                      value={draft.mealRelation}
                      onValueChange={(value) =>
                        update(draft.key, { mealRelation: value as MealRelation }, "mealRelation")
                      }
                    >
                      <SelectTrigger
                        id={id("mealRelation")}
                        className={cn("w-full", flagClass("mealRelation"))}
                        aria-describedby={id("mealRelation-hint")}
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {MEAL_RELATION_OPTIONS.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FieldDescription id={id("mealRelation-hint")}>
                      Only what your prescription says. If it says nothing, leave &quot;No food requirement&quot; and
                      MedGuard will use standard guidance.
                    </FieldDescription>
                  </Field>

                  {draft.instructions && (
                    <p className="text-sm text-muted-foreground sm:col-span-2">
                      <span className="font-medium text-foreground">Written instructions:</span> {draft.instructions}
                    </p>
                  )}
                </div>
              </fieldset>
            </li>
          );
        })}
      </ol>

      <Button type="button" variant="outline" onClick={add} className="w-full sm:w-auto">
        <Plus data-icon="inline-start" aria-hidden />
        Add another medicine
      </Button>

      <div className="flex flex-col-reverse gap-3 border-t border-border pt-6 sm:flex-row sm:justify-between">
        <Button type="button" variant="ghost" onClick={onBack}>
          Back
        </Button>
        <Button type="button" size="lg" onClick={submit}>
          These are correct
        </Button>
      </div>
    </div>
  );
}

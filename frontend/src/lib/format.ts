import type { MealRelation, Severity, Source } from "@/lib/types";

export const MEAL_RELATION_LABELS: Record<MealRelation, string> = {
  any: "No food requirement",
  with_food: "With food",
  before_meal: "30–60 min before a meal",
  empty_stomach: "Empty stomach",
  before_bedtime: "At bedtime",
};

export const MEAL_RELATION_OPTIONS: { value: MealRelation; label: string }[] = (
  ["any", "with_food", "before_meal", "empty_stomach", "before_bedtime"] as const
).map((value) => ({ value, label: MEAL_RELATION_LABELS[value] }));

export const SOURCE_LABELS: Record<Source, string> = {
  dataset: "MedGuard dataset",
  curated_rule: "Timing rule",
  ai: "AI-identified",
};

export const SEVERITY_ORDER: Severity[] = ["High", "Medium", "Low"];

export const SEVERITY_LABELS: Record<Severity, string> = {
  High: "High risk",
  Medium: "Medium risk",
  Low: "Low risk",
};

export function formatGap(minutes: number) {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} h ${rest} min` : `${hours} h`;
}

export function formatDate(iso: string) {
  return new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" }).format(new Date(iso));
}

export function frequencyLabel(dosesPerDay: number | null, asNeeded: boolean) {
  if (asNeeded) return "As needed";
  if (!dosesPerDay) return "Frequency missing";
  return dosesPerDay === 1 ? "Once a day" : `${dosesPerDay} times a day`;
}

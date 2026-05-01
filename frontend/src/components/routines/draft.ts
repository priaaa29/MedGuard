import type { DailySchedule, ExtractedMedication, MealRelation, Medication } from "@/lib/types";

/** A medicine row being edited in the wizard. */
export type DraftMedication = {
  key: string;
  name: string;
  genericName: string;
  strength: string;
  dose: string;
  /** "1".."6", "prn" for as-needed, or "" when unknown. */
  frequency: string;
  mealRelation: MealRelation;
  instructions: string;
  /** Fields the AI couldn't read clearly; shown highlighted until edited. */
  uncertain: string[];
};

export type DraftErrors = Partial<Record<"name" | "frequency", string>>;

export const DEFAULT_SCHEDULE: DailySchedule = {
  wake: "07:00",
  breakfast: "08:00",
  lunch: "13:00",
  dinner: "20:00",
  sleep: "22:30",
};

let counter = 0;
const newKey = () => `med-${Date.now()}-${counter++}`;

export function emptyDraft(): DraftMedication {
  return {
    key: newKey(),
    name: "",
    genericName: "",
    strength: "",
    dose: "",
    frequency: "",
    mealRelation: "any",
    instructions: "",
    uncertain: [],
  };
}

const UNCERTAIN_FIELD_MAP: Record<string, string> = {
  name: "name",
  generic_name: "genericName",
  strength: "strength",
  dose: "dose",
  doses_per_day: "frequency",
  as_needed: "frequency",
  meal_relation: "mealRelation",
  instructions: "instructions",
};

export function fromExtracted(med: ExtractedMedication): DraftMedication {
  return {
    key: newKey(),
    name: med.name,
    genericName: med.generic_name ?? "",
    strength: med.strength ?? "",
    dose: med.dose ?? "",
    frequency: med.as_needed ? "prn" : med.doses_per_day ? String(Math.min(med.doses_per_day, 6)) : "",
    mealRelation: med.meal_relation,
    instructions: [med.instructions, med.duration ? `For ${med.duration}` : null].filter(Boolean).join(". "),
    uncertain: med.uncertain_fields.map((field) => UNCERTAIN_FIELD_MAP[field] ?? field),
  };
}

export function validateDrafts(drafts: DraftMedication[]): Record<string, DraftErrors> {
  const errors: Record<string, DraftErrors> = {};
  const seen = new Set<string>();
  for (const draft of drafts) {
    const found: DraftErrors = {};
    const name = draft.name.trim().toLowerCase();
    if (!name) found.name = "Enter the medicine name.";
    else if (seen.has(name)) found.name = "This medicine is already listed.";
    seen.add(name);
    if (!draft.frequency) found.frequency = "Choose how often it's taken.";
    if (Object.keys(found).length) errors[draft.key] = found;
  }
  return errors;
}

const orNull = (value: string) => value.trim() || null;

export function toMedication(draft: DraftMedication): Medication {
  const asNeeded = draft.frequency === "prn";
  return {
    name: draft.name.trim(),
    generic_name: orNull(draft.genericName),
    strength: orNull(draft.strength),
    dose: orNull(draft.dose),
    doses_per_day: asNeeded ? null : Number(draft.frequency),
    as_needed: asNeeded,
    meal_relation: draft.mealRelation,
    instructions: orNull(draft.instructions),
  };
}

export function validateSchedule(schedule: DailySchedule): string | null {
  const order: (keyof DailySchedule)[] = ["wake", "breakfast", "lunch", "dinner", "sleep"];
  if (order.some((key) => !schedule[key])) return "Fill in every time.";
  for (let i = 1; i < order.length; i++) {
    if (schedule[order[i]] <= schedule[order[i - 1]]) {
      return "Times need to go in order through one day: wake, breakfast, lunch, dinner, then sleep. Sleep times after midnight aren't supported yet.";
    }
  }
  return null;
}

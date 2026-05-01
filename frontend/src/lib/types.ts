// Mirrors backend/app/schemas.py. Keep in sync when the API changes.

export type MealRelation = "with_food" | "before_meal" | "empty_stomach" | "before_bedtime" | "any";
export type TimeOfDay = "morning" | "evening" | "any";
export type Severity = "High" | "Medium" | "Low";
export type Source = "dataset" | "curated_rule" | "ai";

export type User = { id: string; email: string; created_at: string };

export type ExtractedMedication = {
  name: string;
  generic_name: string | null;
  strength: string | null;
  dose: string | null;
  doses_per_day: number | null;
  as_needed: boolean;
  meal_relation: MealRelation;
  instructions: string | null;
  duration: string | null;
  uncertain_fields: string[];
};

export type PrescriptionExtraction = {
  is_prescription: boolean;
  medications: ExtractedMedication[];
  warnings: string[];
};

export type Medication = {
  name: string;
  generic_name: string | null;
  strength: string | null;
  dose: string | null;
  doses_per_day: number | null;
  as_needed: boolean;
  meal_relation: MealRelation;
  instructions: string | null;
};

export type DailySchedule = {
  wake: string;
  breakfast: string;
  lunch: string;
  dinner: string;
  sleep: string;
};

export type InteractionFinding = {
  medicine: string;
  interacts_with: string;
  kind: "food" | "drug";
  severity: Severity;
  effect: string;
  recommendation: string;
  source: Source;
};

export type Separation = {
  medicine_a: string;
  medicine_b: string;
  a_first_minutes: number;
  b_first_minutes: number;
  reason: string;
  source: Source;
};

export type MedicationConstraint = {
  medicine: string;
  doses_per_day: number;
  meal_relation: MealRelation;
  meal_relation_source: "prescription" | "curated_rule" | "ai" | "default";
  time_of_day: TimeOfDay;
  min_gap_minutes: number;
};

export type ScheduledDose = { medicine: string; time: string; dose: string | null; note: string };
export type ValidationIssue = { code: string; medicine: string | null; message: string };

export type Routine = {
  valid: boolean;
  doses: ScheduledDose[];
  as_needed: string[];
  food_guidance: string[];
  summary: string;
  issues: ValidationIssue[];
  attempts: number;
};

export type AnalysisResult = {
  medications: Medication[];
  interactions: InteractionFinding[];
  constraints: { medications: MedicationConstraint[]; separations: Separation[] };
  routine: Routine;
  warnings: string[];
  safety_modifications: string[];
  disclaimer: string;
};

export type RoutineStatus = "pending" | "ready" | "failed";

export type RoutineSummary = {
  id: string;
  title: string;
  status: RoutineStatus;
  medicines: string[];
  /** Null until the routine is ready. */
  valid: boolean | null;
  dose_count: number;
  created_at: string;
  updated_at: string;
};

export type RoutineDetail = {
  id: string;
  title: string;
  status: RoutineStatus;
  /** User-safe reason when status is "failed". */
  error: string | null;
  medications: Medication[];
  schedule: DailySchedule;
  /** Null until the routine is ready. */
  result: AnalysisResult | null;
  created_at: string;
  updated_at: string;
};

"""Data models shared by the API, the Claude calls and the scheduler.

Models named *Draft / *Review / Extracted* are what Claude returns (used as
structured-output schemas). Everything else is validated application data.
"""

from datetime import UTC, datetime, time
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, EmailStr, Field, field_serializer, field_validator, model_validator

from app.config import MAX_MEDICATIONS, PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH

MealRelation = Literal["with_food", "before_meal", "empty_stomach", "before_bedtime", "any"]
TimeOfDay = Literal["morning", "evening", "any"]
Severity = Literal["High", "Medium", "Low"]
Source = Literal["dataset", "curated_rule", "ai"]


def _as_utc(value: datetime) -> datetime:
    # The database stores naive UTC; make that explicit so clients don't read it as local time.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


UTCDateTime = Annotated[datetime, AfterValidator(_as_utc)]

MEAL_RELATION_HELP = (
    "with_food = with or just after a meal; before_meal = 30-60 minutes before a meal; "
    "empty_stomach = at least 1 hour before or 2 hours after food; "
    "before_bedtime = within the hour before sleep; any = no food requirement stated."
)


# --------------------------------------------------------------------------- #
# Prescription extraction (Claude output)
# --------------------------------------------------------------------------- #
class ExtractedMedication(BaseModel):
    name: str = Field(description="Medicine name exactly as written on the prescription.")
    generic_name: str | None = Field(
        description="Generic (international non-proprietary) name if you are confident, else null."
    )
    strength: str | None = Field(description="Strength per unit, e.g. '500 mg'. Null if not written.")
    dose: str | None = Field(description="Amount per dose, e.g. '1 tablet'. Null if not written.")
    doses_per_day: int | None = Field(
        description="Number of scheduled doses per day. Null if as-needed or not clearly written."
    )
    as_needed: bool = Field(description="True for PRN / SOS / 'as needed' medicines.")
    meal_relation: MealRelation = Field(description=MEAL_RELATION_HELP)
    instructions: str | None = Field(description="Any other written instructions, verbatim.")
    duration: str | None = Field(description="Course length if written, e.g. '5 days'.")
    uncertain_fields: list[str] = Field(
        description="Names of fields above that were hard to read or ambiguous."
    )


class PrescriptionExtraction(BaseModel):
    is_prescription: bool = Field(
        description="False if the input is not a prescription or medicine list."
    )
    medications: list[ExtractedMedication]
    warnings: list[str] = Field(
        description="Illegible sections or anything the user should double-check."
    )


# --------------------------------------------------------------------------- #
# User-confirmed input
# --------------------------------------------------------------------------- #
class Medication(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    generic_name: str | None = Field(default=None, max_length=120)
    strength: str | None = Field(default=None, max_length=60)
    dose: str | None = Field(default=None, max_length=60)
    doses_per_day: int | None = Field(default=None, ge=1, le=6)
    as_needed: bool = False
    meal_relation: MealRelation = "any"
    instructions: str | None = Field(default=None, max_length=300)

    @field_validator("name", "generic_name")
    @classmethod
    def strip_names(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_frequency(self):
        if not self.as_needed and self.doses_per_day is None:
            raise ValueError(
                f"{self.name}: doses_per_day is required unless the medicine is taken as needed"
            )
        return self


class DailySchedule(BaseModel):
    wake: time
    breakfast: time
    lunch: time
    dinner: time
    sleep: time

    @model_validator(mode="after")
    def check_order(self):
        order = [self.wake, self.breakfast, self.lunch, self.dinner, self.sleep]
        if order != sorted(order) or len(set(order)) != len(order):
            raise ValueError(
                "Times must be in order: wake < breakfast < lunch < dinner < sleep, within "
                "one day (overnight schedules are not supported yet)"
            )
        return self

    @field_serializer("wake", "breakfast", "lunch", "dinner", "sleep")
    def serialize_time(self, value: time) -> str:
        return value.strftime("%H:%M")


class AnalyzeRequest(BaseModel):
    medications: list[Medication] = Field(min_length=1, max_length=MAX_MEDICATIONS)
    schedule: DailySchedule

    @model_validator(mode="after")
    def unique_names(self):
        names = [med.name.lower() for med in self.medications]
        if len(names) != len(set(names)):
            raise ValueError("Each medicine can only be listed once")
        return self


# --------------------------------------------------------------------------- #
# Interaction review (Claude output)
# --------------------------------------------------------------------------- #
class AIInteraction(BaseModel):
    medicine: str = Field(description="One of the given medicine names, exactly as given.")
    interacts_with: str = Field(description="The food, drink or other given medicine.")
    kind: Literal["food", "drug"]
    severity: Severity
    effect: str = Field(description="One plain-language sentence on what happens.")
    recommendation: str = Field(description="One practical sentence on what to do.")


class AISeparation(BaseModel):
    medicine_a: str = Field(description="One of the given medicine names, exactly as given.")
    medicine_b: str = Field(description="Another given medicine name, exactly as given.")
    a_first_minutes: int = Field(
        description="Minimum minutes medicine_b must wait after a dose of medicine_a."
    )
    b_first_minutes: int = Field(
        description="Minimum minutes medicine_a must wait after a dose of medicine_b."
    )
    reason: str


class AIMealGuidance(BaseModel):
    medicine: str = Field(description="One of the given medicine names, exactly as given.")
    meal_relation: MealRelation = Field(description=MEAL_RELATION_HELP)
    time_of_day: TimeOfDay
    reason: str


class InteractionReview(BaseModel):
    interactions: list[AIInteraction]
    separations: list[AISeparation]
    meal_guidance: list[AIMealGuidance]


# --------------------------------------------------------------------------- #
# Findings and constraints (application data)
# --------------------------------------------------------------------------- #
class InteractionFinding(BaseModel):
    medicine: str
    interacts_with: str
    kind: Literal["food", "drug"]
    severity: Severity
    effect: str
    recommendation: str
    source: Source


class Separation(BaseModel):
    medicine_a: str
    medicine_b: str
    a_first_minutes: int = Field(ge=0, le=720)
    b_first_minutes: int = Field(ge=0, le=720)
    reason: str
    source: Source


class MedicationConstraint(BaseModel):
    medicine: str
    doses_per_day: int
    meal_relation: MealRelation
    meal_relation_source: Literal["prescription", "curated_rule", "ai", "default"]
    time_of_day: TimeOfDay
    min_gap_minutes: int


class ConstraintSet(BaseModel):
    medications: list[MedicationConstraint]
    separations: list[Separation]


# --------------------------------------------------------------------------- #
# Routine
# --------------------------------------------------------------------------- #
class DraftDose(BaseModel):
    medicine: str = Field(description="One of the given medicine names, exactly as given.")
    time: str = Field(description="24-hour time, HH:MM.")
    note: str = Field(description="Short practical instruction, at most 15 words.")


class RoutineDraft(BaseModel):
    doses: list[DraftDose]
    food_guidance: list[str] = Field(
        description="Practical food/drink reminders based only on the listed interactions."
    )
    summary: str = Field(description="Two or three plain sentences explaining the timetable.")


class ScheduledDose(BaseModel):
    medicine: str
    time: str
    dose: str | None
    note: str


class ValidationIssue(BaseModel):
    code: str
    medicine: str | None = None
    message: str


class Routine(BaseModel):
    valid: bool
    doses: list[ScheduledDose]
    as_needed: list[str]
    food_guidance: list[str]
    summary: str
    issues: list[ValidationIssue]
    attempts: int


class AnalysisResult(BaseModel):
    medications: list[Medication]
    interactions: list[InteractionFinding]
    constraints: ConstraintSet
    routine: Routine
    warnings: list[str]
    safety_modifications: list[str]
    disclaimer: str


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.lower()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.lower()


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class UserOut(BaseModel):
    id: str
    email: str
    created_at: UTCDateTime


# --------------------------------------------------------------------------- #
# Saved routines
# --------------------------------------------------------------------------- #
class CreateRoutineRequest(AnalyzeRequest):
    title: str | None = Field(default=None, max_length=100)


class RenameRoutineRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)


RoutineStatus = Literal["pending", "ready", "failed"]


class RoutineSummary(BaseModel):
    id: str
    title: str
    status: RoutineStatus
    medicines: list[str]
    # Null until the routine is ready.
    valid: bool | None
    dose_count: int
    created_at: UTCDateTime
    updated_at: UTCDateTime


class RoutineDetail(BaseModel):
    id: str
    title: str
    status: RoutineStatus
    # User-safe reason when status is "failed".
    error: str | None
    medications: list[Medication]
    schedule: DailySchedule
    result: AnalysisResult | None
    created_at: UTCDateTime
    updated_at: UTCDateTime

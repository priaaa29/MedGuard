"""End-to-end analysis: interactions -> constraints -> routine -> safety checks.

  curated dataset + timing rules   (deterministic)
        -> Claude interaction review (fills gaps, labelled "ai")
        -> constraint set            (deterministic merge, fixed precedence)
        -> Claude routine draft      (proposal)
        -> validator                 (deterministic accept/reject, one retry)
        -> safety scrub              (removes dose-change / stop / diagnosis text)
"""

import logging

from app.core import dataset
from app.core.safety import DISCLAIMER, HIGH_RISK_WARNING, scrub
from app.llm.client import LLMError, StructuredLLM
from app.llm.review import review_interactions
from app.llm.routine import generate_routine
from app.scheduling import rules
from app.scheduling.constraints import build_constraints, name_resolver
from app.scheduling.validator import to_minutes, validate_routine
from app.schemas import (
    AnalysisResult,
    AnalyzeRequest,
    ConstraintSet,
    DailySchedule,
    InteractionFinding,
    InteractionReview,
    Medication,
    Routine,
    RoutineDraft,
    ScheduledDose,
    ValidationIssue,
)

logger = logging.getLogger(__name__)

MAX_ROUTINE_ATTEMPTS = 2
FALLBACK_RECOMMENDATION = "Ask your doctor or pharmacist how to manage this."
INVALID_ROUTINE_SUMMARY = (
    "MedGuard could not build a timetable that meets every timing rule for these medicines. "
    "Do not follow the times below; show this list to your pharmacist so they can plan the "
    "timing with you."
)


class _Scrubber:
    def __init__(self):
        self.modifications: list[str] = []

    def __call__(self, text: str, where: str) -> str:
        clean, codes = scrub(text)
        for code in codes:
            self.modifications.append(f"removed {code} text from {where}")
        return clean


def _ai_findings(
    review: InteractionReview | None,
    medications: list[Medication],
    known: list[InteractionFinding],
    scrubber: _Scrubber,
) -> list[InteractionFinding]:
    if review is None:
        return []
    resolve = name_resolver(medications)
    seen = {(f.medicine.lower(), f.interacts_with.lower()) for f in known}
    findings = []
    for item in review.interactions:
        name = resolve(item.medicine)
        key = (name.lower() if name else "", item.interacts_with.strip().lower())
        if not name or key in seen:
            continue
        seen.add(key)
        where = f"AI interaction note for {name}"
        findings.append(
            InteractionFinding(
                medicine=name,
                interacts_with=item.interacts_with.strip(),
                kind=item.kind,
                severity=item.severity,
                effect=scrubber(item.effect, where),
                recommendation=scrubber(item.recommendation, where) or FALLBACK_RECOMMENDATION,
                source="ai",
            )
        )
    return findings


def _dose_label(medication: Medication) -> str | None:
    parts = [p for p in (medication.dose, f"({medication.strength})" if medication.strength else None) if p]
    return " ".join(parts) or None


def _build_routine(
    llm: StructuredLLM,
    medications: list[Medication],
    constraints: ConstraintSet,
    schedule: DailySchedule,
    findings: list[InteractionFinding],
    scrubber: _Scrubber,
) -> Routine:
    as_needed = [m.name for m in medications if m.as_needed]
    if not constraints.medications:
        return Routine(
            valid=True,
            doses=[],
            as_needed=as_needed,
            food_guidance=[],
            summary="There are no daily medicines to schedule.",
            issues=[],
            attempts=0,
        )

    draft: RoutineDraft | None = None
    issues: list[ValidationIssue] = []
    attempts = 0
    for _ in range(MAX_ROUTINE_ATTEMPTS):
        attempts += 1
        try:
            draft = generate_routine(llm, constraints, schedule, findings, draft, issues)
        except LLMError as exc:
            issues = issues + [ValidationIssue(code="ai_unavailable", message=str(exc))]
            break
        issues = validate_routine(draft.doses, constraints, schedule)
        if not issues:
            break
        logger.info("routine attempt %s rejected: %s", attempts, [i.code for i in issues])

    valid = draft is not None and not issues
    resolve = name_resolver(medications)
    by_name = {m.name: m for m in medications}
    doses = []
    if draft is not None:
        for dose in draft.doses:
            name = resolve(dose.medicine)
            if not name or name not in {c.medicine for c in constraints.medications}:
                continue
            try:
                to_minutes(dose.time)
            except ValueError:
                continue
            doses.append(
                ScheduledDose(
                    medicine=name,
                    time=dose.time.strip(),
                    # Amount always comes from the confirmed prescription, never the model.
                    dose=_dose_label(by_name[name]),
                    note=scrubber(dose.note, f"note for {name}"),
                )
            )
    doses.sort(key=lambda d: (to_minutes(d.time), d.medicine.lower()))

    food_guidance = []
    if draft is not None:
        for line in draft.food_guidance:
            clean = scrubber(line, "food guidance")
            if clean:
                food_guidance.append(clean)

    summary = scrubber(draft.summary, "routine summary") if valid else INVALID_ROUTINE_SUMMARY

    return Routine(
        valid=valid,
        doses=doses,
        as_needed=as_needed,
        food_guidance=food_guidance,
        summary=summary,
        issues=issues,
        attempts=attempts,
    )


def analyze(llm: StructuredLLM, request: AnalyzeRequest) -> AnalysisResult:
    medications, schedule = request.medications, request.schedule
    warnings: list[str] = []
    scrubber = _Scrubber()

    dataset_findings = [f for med in medications for f in dataset.food_interactions(med)]
    curated_separations = rules.curated_separations(medications)

    review = None
    try:
        review = review_interactions(llm, medications, dataset_findings, curated_separations)
    except LLMError as exc:
        warnings.append(f"AI interaction review unavailable: {exc} Showing curated data only.")

    findings = dataset_findings + _ai_findings(review, medications, dataset_findings, scrubber)
    constraints, as_needed_separations = build_constraints(medications, schedule, review)
    routine = _build_routine(llm, medications, constraints, schedule, findings, scrubber)

    for sep in as_needed_separations:
        warnings.append(f"If you take {sep.medicine_a} and {sep.medicine_b} on the same day: {sep.reason}")
    if any(f.severity == "High" for f in findings):
        warnings.insert(0, HIGH_RISK_WARNING)

    return AnalysisResult(
        medications=medications,
        interactions=findings,
        constraints=constraints,
        routine=routine,
        warnings=warnings,
        safety_modifications=scrubber.modifications,
        disclaimer=DISCLAIMER,
    )

"""Saved routines.

Building a routine can make several AI calls and take over a minute,
longer than proxies like Vercel will hold a request open. So creation is a
background job: POST returns 202 with status "pending", the client polls
GET /api/routines/{id} until it's "ready" or "failed".
"""

import logging
from datetime import timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import current_user, enforce_limit, get_llm, get_session_factory
from app.config import ROUTINE_STALE_MINUTES, ROUTINES_PER_HOUR
from app.db import get_db, utcnow
from app.llm.client import StructuredLLM
from app.models import SavedRoutine, User
from app.pipeline import analyze
from app.schemas import (
    AnalysisResult,
    AnalyzeRequest,
    CreateRoutineRequest,
    DailySchedule,
    Medication,
    RenameRoutineRequest,
    RoutineDetail,
    RoutineSummary,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/routines", tags=["routines"])

MAX_SAVED_ROUTINES = 50
GENERIC_FAILURE = "Something went wrong while building this routine. Please try again."
STALE_FAILURE = "Building this routine took too long and was stopped. Please try again."


# --------------------------------------------------------------------------- #
# Background job
# --------------------------------------------------------------------------- #
def build_routine(routine_id: str, llm: StructuredLLM, session_factory: sessionmaker) -> None:
    """Run the analysis for a pending routine and store the outcome."""
    with session_factory() as db:
        row = db.get(SavedRoutine, routine_id)
        if row is None or row.status != "pending":
            return
        request = AnalyzeRequest(
            medications=[Medication.model_validate(m) for m in row.medications],
            schedule=DailySchedule.model_validate(row.schedule),
        )

    # The AI calls happen with no database session held open.
    status, error, result = "failed", GENERIC_FAILURE, None
    try:
        analysis = analyze(llm, request)
        unavailable = [i for i in analysis.routine.issues if i.code == "ai_unavailable"]
        if unavailable and not analysis.routine.doses:
            error = unavailable[0].message
        else:
            status, error, result = "ready", None, analysis
    except Exception:  # noqa: BLE001 - a job must always end in a final state
        logger.exception("routine %s failed", routine_id)

    with session_factory() as db:
        row = db.get(SavedRoutine, routine_id)
        if row is None or row.status != "pending":  # deleted or marked stale meanwhile
            return
        row.status = status
        row.error = error
        row.result = result.model_dump(mode="json") if result else None
        row.valid = result.routine.valid if result else None
        db.commit()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _default_title(body: CreateRoutineRequest) -> str:
    names = ", ".join(m.name for m in body.medications)
    return names if len(names) <= 100 else names[:97] + "..."


def _expire_if_stale(db: Session, row: SavedRoutine) -> None:
    if row.status == "pending" and row.updated_at < utcnow() - timedelta(minutes=ROUTINE_STALE_MINUTES):
        row.status, row.error = "failed", STALE_FAILURE
        db.commit()


def _summary(row: SavedRoutine) -> RoutineSummary:
    return RoutineSummary(
        id=row.id,
        title=row.title,
        status=row.status,
        medicines=[m["name"] for m in row.medications],
        valid=row.valid,
        dose_count=len(row.result["routine"]["doses"]) if row.result else 0,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _detail(row: SavedRoutine) -> RoutineDetail:
    return RoutineDetail(
        id=row.id,
        title=row.title,
        status=row.status,
        error=row.error,
        medications=[Medication.model_validate(m) for m in row.medications],
        schedule=DailySchedule.model_validate(row.schedule),
        result=AnalysisResult.model_validate(row.result) if row.result else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _owned(db: Session, user: User, routine_id: str) -> SavedRoutine:
    # Filter by owner in the query itself; someone else's id looks the same as a missing one.
    row = db.scalar(
        select(SavedRoutine).where(SavedRoutine.id == routine_id, SavedRoutine.user_id == user.id)
    )
    if row is None:
        raise HTTPException(404, "Routine not found.")
    return row


def _check_routine_limit(user: User) -> None:
    enforce_limit(
        f"routine:{user.id}", ROUTINES_PER_HOUR, 3600,
        "You've created a lot of routines this hour. Please try again later.",
    )


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@router.post("", response_model=RoutineDetail, status_code=202)
def create_routine(
    body: CreateRoutineRequest,
    background: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    llm: StructuredLLM = Depends(get_llm),
    session_factory: sessionmaker = Depends(get_session_factory),
):
    """Save the confirmed medicines and start building the routine in the background."""
    count = db.scalar(select(func.count()).select_from(SavedRoutine).where(SavedRoutine.user_id == user.id))
    if count >= MAX_SAVED_ROUTINES:
        raise HTTPException(409, f"You can save up to {MAX_SAVED_ROUTINES} routines. Delete one to add another.")
    _check_routine_limit(user)

    row = SavedRoutine(
        user_id=user.id,
        title=(body.title or "").strip() or _default_title(body),
        medications=[m.model_dump(mode="json") for m in body.medications],
        schedule=body.schedule.model_dump(mode="json"),
        status="pending",
    )
    db.add(row)
    db.commit()
    background.add_task(build_routine, row.id, llm, session_factory)
    return _detail(row)


@router.post("/{routine_id}/retry", response_model=RoutineDetail, status_code=202)
def retry_routine(
    routine_id: str,
    background: BackgroundTasks,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    llm: StructuredLLM = Depends(get_llm),
    session_factory: sessionmaker = Depends(get_session_factory),
):
    row = _owned(db, user, routine_id)
    _expire_if_stale(db, row)
    if row.status != "failed":
        raise HTTPException(409, "Only a routine that failed can be retried.")
    _check_routine_limit(user)
    row.status, row.error, row.result, row.valid = "pending", None, None, None
    db.commit()
    background.add_task(build_routine, row.id, llm, session_factory)
    return _detail(row)


@router.get("", response_model=list[RoutineSummary])
def list_routines(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(SavedRoutine)
        .where(SavedRoutine.user_id == user.id)
        .order_by(SavedRoutine.created_at.desc())
    ).all()
    for row in rows:
        _expire_if_stale(db, row)
    return [_summary(row) for row in rows]


@router.get("/{routine_id}", response_model=RoutineDetail)
def get_routine(routine_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = _owned(db, user, routine_id)
    _expire_if_stale(db, row)
    return _detail(row)


@router.patch("/{routine_id}", response_model=RoutineSummary)
def rename_routine(
    routine_id: str,
    body: RenameRoutineRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    row = _owned(db, user, routine_id)
    row.title = body.title.strip()
    db.commit()
    return _summary(row)


@router.delete("/{routine_id}", status_code=204)
def delete_routine(routine_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = _owned(db, user, routine_id)
    db.delete(row)
    db.commit()

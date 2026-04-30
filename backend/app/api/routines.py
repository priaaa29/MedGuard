from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, enforce_limit, get_llm
from app.config import ROUTINES_PER_HOUR
from app.db import get_db
from app.llm.client import StructuredLLM
from app.models import SavedRoutine, User
from app.pipeline import analyze
from app.schemas import (
    AnalysisResult,
    CreateRoutineRequest,
    DailySchedule,
    RenameRoutineRequest,
    RoutineDetail,
    RoutineSummary,
)

router = APIRouter(prefix="/api/routines", tags=["routines"])

MAX_SAVED_ROUTINES = 50


def _default_title(body: CreateRoutineRequest) -> str:
    names = ", ".join(m.name for m in body.medications)
    return names if len(names) <= 100 else names[:97] + "..."


def _summary(row: SavedRoutine) -> RoutineSummary:
    return RoutineSummary(
        id=row.id,
        title=row.title,
        medicines=[m["name"] for m in row.medications],
        valid=row.valid,
        dose_count=len(row.result["routine"]["doses"]),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _detail(row: SavedRoutine) -> RoutineDetail:
    return RoutineDetail(
        id=row.id,
        title=row.title,
        schedule=DailySchedule.model_validate(row.schedule),
        result=AnalysisResult.model_validate(row.result),
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


@router.post("", response_model=RoutineDetail, status_code=201)
def create_routine(
    body: CreateRoutineRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    llm: StructuredLLM = Depends(get_llm),
):
    """Check interactions, build the timetable and save it to the account."""
    count = db.scalar(select(func.count()).select_from(SavedRoutine).where(SavedRoutine.user_id == user.id))
    if count >= MAX_SAVED_ROUTINES:
        raise HTTPException(409, f"You can save up to {MAX_SAVED_ROUTINES} routines. Delete one to add another.")
    enforce_limit(
        f"routine:{user.id}", ROUTINES_PER_HOUR, 3600,
        "You've created a lot of routines this hour. Please try again later.",
    )

    # Plain def endpoint: runs in a worker thread, so the blocking Claude calls are fine.
    result = analyze(llm, body)
    unavailable = [i for i in result.routine.issues if i.code == "ai_unavailable"]
    if unavailable and not result.routine.doses:
        # Nothing worth saving; let the user retry instead of storing an empty routine.
        raise HTTPException(502, unavailable[0].message)

    row = SavedRoutine(
        user_id=user.id,
        title=(body.title or "").strip() or _default_title(body),
        medications=[m.model_dump(mode="json") for m in body.medications],
        schedule=body.schedule.model_dump(mode="json"),
        result=result.model_dump(mode="json"),
        valid=result.routine.valid,
    )
    db.add(row)
    db.commit()
    return _detail(row)


@router.get("", response_model=list[RoutineSummary])
def list_routines(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(SavedRoutine)
        .where(SavedRoutine.user_id == user.id)
        .order_by(SavedRoutine.created_at.desc())
    ).all()
    return [_summary(row) for row in rows]


@router.get("/{routine_id}", response_model=RoutineDetail)
def get_routine(routine_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _detail(_owned(db, user, routine_id))


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

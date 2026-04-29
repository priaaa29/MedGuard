"""Live end-to-end check against the real Claude API (costs a few cents).

    cd backend && .venv/bin/python -m scripts.smoke_test
"""

import json
from datetime import time

from app.llm.client import ClaudeLLM
from app.llm.extract import extract_from_text
from app.pipeline import analyze
from app.schemas import AnalyzeRequest, DailySchedule, Medication

PRESCRIPTION = """Rx
1. Tab Thyronorm 50 mcg   1-0-0  empty stomach   x 3 months
2. Tab Glucophage 500 mg  1-0-1  after food      x 1 month
3. Tab Shelcal 500        0-1-0                  x 1 month
4. Cap Doxycycline 100 mg BD                     x 7 days
5. Tab Dolo 650 SOS for fever
"""


def main():
    llm = ClaudeLLM()

    print("== extract ==")
    extraction = extract_from_text(llm, PRESCRIPTION)
    print(extraction.model_dump_json(indent=2))

    medications = [
        Medication(**m.model_dump(exclude={"duration", "uncertain_fields"}))
        for m in extraction.medications
        if m.as_needed or m.doses_per_day
    ]
    schedule = DailySchedule(
        wake=time(6, 30), breakfast=time(8, 0), lunch=time(13, 30), dinner=time(20, 30), sleep=time(23, 0)
    )

    print("\n== analyze ==")
    result = analyze(llm, AnalyzeRequest(medications=medications, schedule=schedule))
    print(json.dumps(result.model_dump(mode="json"), indent=2))
    print("\nroutine valid:", result.routine.valid, "attempts:", result.routine.attempts)


if __name__ == "__main__":
    main()

import json
from datetime import datetime, timezone
from pathlib import Path


LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "audit.jsonl"


def log_query(
    user_id,
    query,
    medicine_name,
    risk_level,
    confidence_score,
    was_blocked,
    modifications,
    agent_trace,
):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "query": query,
        "medicine": medicine_name,
        "risk_level": risk_level,
        "confidence_score": confidence_score,
        "safe_to_display": not was_blocked,
        "was_blocked": was_blocked,
        "modifications": modifications,
        "agent_trace": agent_trace,
    }

    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry) + "\n")

    return entry


def get_recent_audit_entries(limit=5):
    if not LOG_PATH.exists():
        return []

    with LOG_PATH.open("r", encoding="utf-8") as file:
        lines = file.readlines()[-limit:]

    entries = []
    for line in lines:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    return list(reversed(entries))

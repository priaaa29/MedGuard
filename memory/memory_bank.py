import sqlite3
import sys
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "medguard_memory.db"
SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.append(str(SRC_PATH))


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_medicines (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                medicine_name TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, medicine_name)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS interaction_history (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                query TEXT NOT NULL,
                medicine_name TEXT,
                risk_level TEXT,
                confidence_score INTEGER,
                queried_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def add_medicine(user_id, medicine_name):
    init_db()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO user_medicines (user_id, medicine_name)
            VALUES (?, ?)
            """,
            (user_id.strip(), medicine_name.strip()),
        )


def get_user_medicines(user_id):
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT medicine_name, added_at
            FROM user_medicines
            WHERE user_id = ?
            ORDER BY added_at DESC, medicine_name ASC
            """,
            (user_id.strip(),),
        ).fetchall()

    return [dict(row) for row in rows]


def log_interaction(user_id, query, medicine_name, risk_level, confidence_score):
    init_db()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO interaction_history (
                user_id,
                query,
                medicine_name,
                risk_level,
                confidence_score
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id.strip(),
                query.strip(),
                medicine_name,
                risk_level,
                int(round(confidence_score)),
            ),
        )


def get_history(user_id, limit=5):
    init_db()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT query, medicine_name, risk_level, confidence_score, queried_at
            FROM interaction_history
            WHERE user_id = ?
            ORDER BY queried_at DESC, id DESC
            LIMIT ?
            """,
            (user_id.strip(), limit),
        ).fetchall()

    return [dict(row) for row in rows]


def get_profile_stats(user_id):
    init_db()
    with get_connection() as connection:
        medicine_count = connection.execute(
            "SELECT COUNT(*) FROM user_medicines WHERE user_id = ?",
            (user_id.strip(),),
        ).fetchone()[0]
        query_count = connection.execute(
            "SELECT COUNT(*) FROM interaction_history WHERE user_id = ?",
            (user_id.strip(),),
        ).fetchone()[0]
        high_risk_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM interaction_history
            WHERE user_id = ? AND risk_level = 'High'
            """,
            (user_id.strip(),),
        ).fetchone()[0]

    memory_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
    return {
        "medicine_count": medicine_count,
        "query_count": query_count,
        "high_risk_count": high_risk_count,
        "memory_size_bytes": memory_size,
    }


def check_cross_interactions(user_id):
    from risk_model import get_medicine_info

    saved_medicines = [item["medicine_name"] for item in get_user_medicines(user_id)]
    interaction_index = {}
    conflicts = []

    for medicine_name in saved_medicines:
        result, matched_name, _ = get_medicine_info(medicine_name)
        if result is None or result.empty:
            continue
        interaction_index[matched_name] = result.to_dict("records")

    medicines = list(interaction_index.keys())
    for index, medicine_name in enumerate(medicines):
        for other_medicine in medicines[index + 1 :]:
            for interaction in interaction_index[medicine_name]:
                for other_interaction in interaction_index[other_medicine]:
                    if interaction["Food"] != other_interaction["Food"]:
                        continue

                    conflicts.append(
                        {
                            "medicine": medicine_name,
                            "other_medicine": other_medicine,
                            "shared_food": interaction["Food"],
                            "severity": interaction["Severity"],
                            "other_severity": other_interaction["Severity"],
                            "explanation": (
                                f"Both medicines have known guidance for "
                                f"{interaction['Food']}. {medicine_name}: "
                                f"{interaction['Recommendation']}. "
                                f"{other_medicine}: {other_interaction['Recommendation']}."
                            ),
                        }
                    )

    return conflicts

import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "medguard_memory.db"


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

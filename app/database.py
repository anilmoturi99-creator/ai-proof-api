import hashlib
import sqlite3
from pathlib import Path
from typing import Optional


DB_PATH = Path(__file__).resolve().parent.parent / "records.db"


def get_connection():

    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    with get_connection() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS records (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                request TEXT NOT NULL,

                response TEXT NOT NULL,

                created_at TEXT NOT NULL,

                previous_hash TEXT,

                content_hash TEXT NOT NULL UNIQUE

            )
            """
        )

        conn.commit()


def canonical_content(
    request: str,
    response: str,
    created_at: str,
    previous_hash: Optional[str],
):

    parts = [
        request,
        response,
        created_at,
        previous_hash or "",
    ]

    return "".join(
        f"{len(part)}:{part}"
        for part in parts
    )


def calculate_hash(
    request: str,
    response: str,
    created_at: str,
    previous_hash: Optional[str],
):

    payload = canonical_content(
        request,
        response,
        created_at,
        previous_hash,
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def get_latest_hash():

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT content_hash
            FROM records
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    if row:
        return row["content_hash"]

    return None


def insert_record(
    request: str,
    response: str,
    created_at: str,
):

    previous_hash = get_latest_hash()

    content_hash = calculate_hash(
        request,
        response,
        created_at,
        previous_hash,
    )

    with get_connection() as conn:

        cursor = conn.execute(
            """
            INSERT INTO records
            (
                request,
                response,
                created_at,
                previous_hash,
                content_hash
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                request,
                response,
                created_at,
                previous_hash,
                content_hash,
            ),
        )

        conn.commit()

        record_id = cursor.lastrowid

    return (
        record_id,
        content_hash,
        previous_hash,
    )


def get_record(record_id: int):

    with get_connection() as conn:

        row = conn.execute(
            """
            SELECT *
            FROM records
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()

    if row:
        return dict(row)

    return None


def get_all_records():

    with get_connection() as conn:

        rows = conn.execute(
            """
            SELECT *
            FROM records
            ORDER BY id
            """
        ).fetchall()

    return [dict(row) for row in rows]


def update_record(
    record_id: int,
    request: str,
    response: str,
):

    existing = get_record(record_id)

    if existing is None:
        return False

    new_hash = calculate_hash(
        request,
        response,
        existing["created_at"],
        existing["previous_hash"],
    )

    with get_connection() as conn:

        conn.execute(
            """
            UPDATE records

            SET request = ?,
                response = ?,
                content_hash = ?

            WHERE id = ?
            """,
            (
                request,
                response,
                new_hash,
                record_id,
            ),
        )

        conn.commit()

    return True


def delete_record(record_id: int):

    existing = get_record(record_id)

    if existing is None:
        return False

    with get_connection() as conn:

        conn.execute(
            """
            DELETE FROM records
            WHERE id = ?
            """,
            (record_id,),
        )

        conn.commit()

    return True


def verify_record(record_id: int):

    record = get_record(record_id)

    if record is None:

        return {
            "valid": False,
            "record_id": record_id,
            "message": "Record not found.",
            "broken": [
                "record_not_found"
            ],
        }

    expected_hash = calculate_hash(
        record["request"],
        record["response"],
        record["created_at"],
        record["previous_hash"],
    )

    broken = []

    if expected_hash != record["content_hash"]:

        broken.append(
            "content_hash"
        )

    if record["id"] > 1:

        previous = get_record(
            record["id"] - 1
        )

        if previous is None:

            broken.append(
                "previous_record_missing"
            )

        elif (
            record["previous_hash"]
            != previous["content_hash"]
        ):

            broken.append(
                "previous_hash"
            )

    return {
        "valid": len(broken) == 0,
        "record_id": record_id,
        "message": (
            "Record is intact."
            if len(broken) == 0
            else "Record was altered."
        ),
        "broken": broken,
    }
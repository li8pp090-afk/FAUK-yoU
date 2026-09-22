import sqlite3
from pathlib import Path


def get_connection(db_path: str):
    connection = sqlite3.connect(
        db_path,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row
    return connection


def init_cache_db(db_path: str):
    Path(db_path).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with get_connection(db_path) as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS file_cache (
                mode TEXT NOT NULL,
                source_type TEXT NOT NULL,
                content_id TEXT NOT NULL,
                file_id TEXT NOT NULL,
                PRIMARY KEY (
                    mode,
                    source_type,
                    content_id
                )
            )
            """
        )

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                scope_key TEXT PRIMARY KEY,
                mode TEXT NOT NULL DEFAULT 'default'
            )
            """
        )

        db.commit()


def get_file_record(
    db_path,
    mode,
    source_type,
    content_id,
):
    with get_connection(db_path) as db:
        row = db.execute(
            """
            SELECT file_id
            FROM file_cache
            WHERE mode = ?
              AND source_type = ?
              AND content_id = ?
            """,
            (
                mode,
                source_type,
                content_id,
            ),
        ).fetchone()

    return row["file_id"] if row else None


def save_file_record(
    db_path,
    mode,
    source_type,
    content_id,
    file_id,
):
    with get_connection(db_path) as db:
        db.execute(
            """
            INSERT OR REPLACE INTO file_cache
            (
                mode,
                source_type,
                content_id,
                file_id
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                mode,
                source_type,
                content_id,
                file_id,
            ),
        )

        db.commit()


def ensure_scope(
    db_path,
    scope_key,
):
    with get_connection(db_path) as db:
        db.execute(
            """
            INSERT OR IGNORE INTO settings
            (
                scope_key,
                mode
            )
            VALUES (?, 'default')
            """,
            (scope_key,),
        )

        db.commit()


def get_mode(
    db_path,
    scope_key,
):
    ensure_scope(
        db_path,
        scope_key,
    )

    with get_connection(db_path) as db:
        row = db.execute(
            """
            SELECT mode
            FROM settings
            WHERE scope_key = ?
            """,
            (scope_key,),
        ).fetchone()

    return row["mode"] if row else "default"


def set_mode(
    db_path,
    scope_key,
    mode,
):
    with get_connection(db_path) as db:
        db.execute(
            """
            INSERT INTO settings
            (
                scope_key,
                mode
            )
            VALUES (?, ?)
            ON CONFLICT(scope_key)
            DO UPDATE SET mode = excluded.mode
            """,
            (
                scope_key,
                mode,
            ),
        )

        db.commit()
import sqlite3
import threading
from pathlib import Path

DB_PATH = Path("bot.sqlite3")

_lock = threading.RLock()
_conn = None


def init_db():
    global _conn

    with _lock:
        if _conn is None:
            DB_PATH.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            _conn = sqlite3.connect(
                DB_PATH,
                check_same_thread=False,
            )

            _conn.execute(
                "PRAGMA journal_mode=WAL"
            )

            _conn.execute(
                "PRAGMA foreign_keys=ON"
            )

            _conn.execute(
                """
                CREATE TABLE IF NOT EXISTS modes (
                    scope TEXT PRIMARY KEY,
                    mode TEXT NOT NULL
                    CHECK(mode IN ('normal', 'voice'))
                )
                """
            )

            _conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reply_state (
                    user_id INTEGER PRIMARY KEY,
                    reply_index INTEGER NOT NULL DEFAULT 0
                )
                """
            )

            _conn.execute(
                """
                CREATE TABLE IF NOT EXISTS file_cache (
                    cache_key TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    kind TEXT NOT NULL
                )
                """
            )

            _conn.commit()


def get_mode(scope):
    init_db()

    with _lock:
        row = _conn.execute(
            """
            SELECT mode
            FROM modes
            WHERE scope = ?
            """,
            (scope,),
        ).fetchone()

        if row:
            return row[0]

        return "normal"


def set_mode(scope, mode):
    init_db()

    with _lock:
        _conn.execute(
            """
            INSERT INTO modes(scope, mode)
            VALUES(?, ?)
            ON CONFLICT(scope)
            DO UPDATE SET mode = excluded.mode
            """,
            (
                scope,
                mode,
            ),
        )

        _conn.commit()


def next_reply(user_id, replies):
    init_db()

    with _lock:
        row = _conn.execute(
            """
            SELECT reply_index
            FROM reply_state
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

        if row is None:
            index = 0
        else:
            index = row[0]

        text = replies[index]

        new_index = (
            index + 1
        ) % len(replies)

        _conn.execute(
            """
            INSERT INTO reply_state(
                user_id,
                reply_index
            )
            VALUES(?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET
                reply_index = excluded.reply_index
            """,
            (
                user_id,
                new_index,
            ),
        )

        _conn.commit()

        return text


def get_file_id(cache_key):
    init_db()

    with _lock:
        row = _conn.execute(
            """
            SELECT file_id, kind
            FROM file_cache
            WHERE cache_key = ?
            """,
            (cache_key,),
        ).fetchone()

        return row


def set_file_id(cache_key, file_id, kind):
    init_db()

    with _lock:
        _conn.execute(
            """
            INSERT INTO file_cache(
                cache_key,
                file_id,
                kind
            )
            VALUES(?, ?, ?)
            ON CONFLICT(cache_key)
            DO UPDATE SET
                file_id = excluded.file_id,
                kind = excluded.kind
            """,
            (
                cache_key,
                file_id,
                kind,
            ),
        )

        _conn.commit()
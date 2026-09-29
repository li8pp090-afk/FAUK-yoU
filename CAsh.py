import sqlite3


class Database:
    def __init__(self, connection):
        self.connection = connection
        self.connection.execute(
            "PRAGMA journal_mode=WAL"
        )
        self.connection.execute(
            "PRAGMA foreign_keys=ON"
        )
        self._create_tables()
        self._migrate_file_cache()

    def _create_tables(self):
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS modes (
                scope_key TEXT PRIMARY KEY,
                mode TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reply_counters (
                scope_key TEXT PRIMARY KEY,
                counter INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS normal_file_cache (
                content_key TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                file_unique_id TEXT,
                filename TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS voice_file_cache (
                content_key TEXT PRIMARY KEY,
                file_id TEXT NOT NULL,
                file_unique_id TEXT,
                filename TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def _migrate_file_cache(self):
        exists = self.connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name='file_cache'
            """
        ).fetchone()

        if exists is None:
            return

        rows = self.connection.execute(
            """
            SELECT
                content_key,
                mode,
                file_id,
                file_unique_id,
                filename
            FROM file_cache
            """
        ).fetchall()

        for row in rows:
            (
                content_key,
                mode,
                file_id,
                file_unique_id,
                filename,
            ) = row

            if mode == "normal":
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO
                    normal_file_cache (
                        content_key,
                        file_id,
                        file_unique_id,
                        filename
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        content_key,
                        file_id,
                        file_unique_id,
                        filename,
                    ),
                )

            elif mode == "voice":
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO
                    voice_file_cache (
                        content_key,
                        file_id,
                        file_unique_id,
                        filename
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        content_key,
                        file_id,
                        file_unique_id,
                        filename,
                    ),
                )

        self.connection.execute(
            "DROP TABLE file_cache"
        )
        self.connection.commit()

    def get_mode(
        self,
        scope_key,
        default_mode,
    ):
        row = self.connection.execute(
            """
            SELECT mode
            FROM modes
            WHERE scope_key=?
            """,
            (scope_key,),
        ).fetchone()

        if row is None:
            return default_mode

        return row[0]

    def set_mode(
        self,
        scope_key,
        mode,
    ):
        self.connection.execute(
            """
            INSERT INTO modes (
                scope_key,
                mode
            )
            VALUES (?, ?)
            ON CONFLICT(scope_key)
            DO UPDATE SET mode=excluded.mode
            """,
            (
                scope_key,
                mode,
            ),
        )
        self.connection.commit()

    def next_reply_index(
        self,
        scope_key,
        total,
    ):
        row = self.connection.execute(
            """
            SELECT counter
            FROM reply_counters
            WHERE scope_key=?
            """,
            (scope_key,),
        ).fetchone()

        counter = (
            0
            if row is None
            else row[0]
        )

        self.connection.execute(
            """
            INSERT INTO reply_counters (
                scope_key,
                counter
            )
            VALUES (?, ?)
            ON CONFLICT(scope_key)
            DO UPDATE SET counter=excluded.counter
            """,
            (
                scope_key,
                counter + 1,
            ),
        )

        self.connection.commit()

        return counter % total

    def get_normal_file(
        self,
        content_key,
    ):
        return self.connection.execute(
            """
            SELECT
                file_id,
                file_unique_id,
                filename
            FROM normal_file_cache
            WHERE content_key=?
            """,
            (content_key,),
        ).fetchone()

    def save_normal_file(
        self,
        content_key,
        file_id,
        file_unique_id,
        filename,
    ):
        self.connection.execute(
            """
            INSERT INTO normal_file_cache (
                content_key,
                file_id,
                file_unique_id,
                filename
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(content_key)
            DO UPDATE SET
                file_id=excluded.file_id,
                file_unique_id=excluded.file_unique_id,
                filename=excluded.filename
            """,
            (
                content_key,
                file_id,
                file_unique_id,
                filename,
            ),
        )
        self.connection.commit()

    def delete_normal_file(
        self,
        content_key,
    ):
        self.connection.execute(
            """
            DELETE FROM normal_file_cache
            WHERE content_key=?
            """,
            (content_key,),
        )
        self.connection.commit()

    def get_voice_file(
        self,
        content_key,
    ):
        return self.connection.execute(
            """
            SELECT
                file_id,
                file_unique_id,
                filename
            FROM voice_file_cache
            WHERE content_key=?
            """,
            (content_key,),
        ).fetchone()

    def save_voice_file(
        self,
        content_key,
        file_id,
        file_unique_id,
        filename,
    ):
        self.connection.execute(
            """
            INSERT INTO voice_file_cache (
                content_key,
                file_id,
                file_unique_id,
                filename
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(content_key)
            DO UPDATE SET
                file_id=excluded.file_id,
                file_unique_id=excluded.file_unique_id,
                filename=excluded.filename
            """,
            (
                content_key,
                file_id,
                file_unique_id,
                filename,
            ),
        )
        self.connection.commit()

    def delete_voice_file(
        self,
        content_key,
    ):
        self.connection.execute(
            """
            DELETE FROM voice_file_cache
            WHERE content_key=?
            """,
            (content_key,),
        )
        self.connection.commit()

    def close(self):
        self.connection.close()
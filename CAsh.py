import aiosqlite


async def init_cache_db(db_path: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS file_cache (
                mode TEXT NOT NULL,
                source_type TEXT NOT NULL,
                content_id TEXT NOT NULL,
                file_id TEXT NOT NULL,
                filename TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (mode, source_type, content_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                scope_key TEXT PRIMARY KEY,
                mode TEXT NOT NULL DEFAULT 'default',
                notice_state TEXT NOT NULL DEFAULT 'disabled'
            )
        """)
        await db.commit()


async def get_file_record(
    db_path: str,
    mode: str,
    source_type: str,
    content_id: str,
):
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            SELECT file_id, filename
            FROM file_cache
            WHERE mode = ?
              AND source_type = ?
              AND content_id = ?
            """,
            (mode, source_type, content_id),
        )
        return await cursor.fetchone()


async def save_file_record(
    db_path: str,
    mode: str,
    source_type: str,
    content_id: str,
    file_id: str,
    filename: str | None = None,
):
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO file_cache (
                mode,
                source_type,
                content_id,
                file_id,
                filename
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (
                mode,
                source_type,
                content_id
            )
            DO UPDATE SET
                file_id = excluded.file_id,
                filename = excluded.filename
            """,
            (
                mode,
                source_type,
                content_id,
                file_id,
                filename,
            ),
        )
        await db.commit()


async def ensure_scope(db, scope: str):
    await db.execute(
        """
        INSERT OR IGNORE INTO settings (
            scope_key,
            mode,
            notice_state
        )
        VALUES (?, 'default', 'disabled')
        """,
        (scope,),
    )


async def get_mode(db_path: str, scope: str) -> str:
    async with aiosqlite.connect(db_path) as db:
        await ensure_scope(db, scope)
        await db.commit()

        cursor = await db.execute(
            "SELECT mode FROM settings WHERE scope_key = ?",
            (scope,),
        )
        row = await cursor.fetchone()

    return row[0]


async def set_mode(db_path: str, scope: str, mode: str):
    async with aiosqlite.connect(db_path) as db:
        await ensure_scope(db, scope)

        await db.execute(
            """
            UPDATE settings
            SET mode = ?
            WHERE scope_key = ?
            """,
            (mode, scope),
        )
        await db.commit()


async def get_notice_state(db_path: str, scope: str) -> str:
    async with aiosqlite.connect(db_path) as db:
        await ensure_scope(db, scope)
        await db.commit()

        cursor = await db.execute(
            "SELECT notice_state FROM settings WHERE scope_key = ?",
            (scope,),
        )
        row = await cursor.fetchone()

    return row[0]


async def set_notice_state(db_path: str, scope: str, state: str):
    async with aiosqlite.connect(db_path) as db:
        await ensure_scope(db, scope)

        await db.execute(
            """
            UPDATE settings
            SET notice_state = ?
            WHERE scope_key = ?
            """,
            (state, scope),
        )
        await db.commit()

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
        await db.commit()

async def get_file_record(db_path: str, mode: str, source_type: str, content_id: str):
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute(
            """
            SELECT file_id, filename 
            FROM file_cache 
            WHERE mode = ? AND source_type = ? AND content_id = ?
            """,
            (mode, source_type, content_id)
        )
        return await cur.fetchone()

async def save_file_record(db_path: str, mode: str, source_type: str, content_id: str, file_id: str, filename: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO file_cache (mode, source_type, content_id, file_id, filename)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(mode, source_type, content_id)
            DO UPDATE SET file_id = excluded.file_id, filename = excluded.filename
            """,
            (mode, source_type, content_id, file_id, filename)
        )
        await db.commit()

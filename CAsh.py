import os
import aiosqlite

DB_PATH = os.getenv("DB_PATH", "cache.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS file_cache (
                url_key TEXT PRIMARY KEY,
                file_id TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id INTEGER,
                thread_id INTEGER DEFAULT 0,
                mode TEXT DEFAULT 'normal',
                PRIMARY KEY (chat_id, thread_id)
            )
        """)
        await db.commit()

async def get_cached_file_id(url_key: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT file_id FROM file_cache WHERE url_key = ?", (url_key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def save_file_id(url_key: str, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO file_cache (url_key, file_id) VALUES (?, ?)", (url_key, file_id))
        await db.commit()

async def get_chat_mode(chat_id: int, thread_id: int = 0) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT mode FROM chat_settings WHERE chat_id = ? AND thread_id = ?", (chat_id, thread_id)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else "normal"

async def set_chat_mode(chat_id: int, thread_id: int, mode: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO chat_settings (chat_id, thread_id, mode) VALUES (?, ?, ?)", (chat_id, thread_id, mode))
        await db.commit()

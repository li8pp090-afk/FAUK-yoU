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
            CREATE TABLE IF NOT EXISTS extract_cache (
                input_file_id TEXT PRIMARY KEY,
                voice_file_id TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_settings (
                chat_id INTEGER,
                thread_id INTEGER DEFAULT 0,
                mode TEXT DEFAULT 'normal',
                delete_links INTEGER DEFAULT 0,
                PRIMARY KEY (chat_id, thread_id)
            )
        """)
        try:
            await db.execute("ALTER TABLE chat_settings ADD COLUMN delete_links INTEGER DEFAULT 0")
        except Exception:
            pass
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

async def get_extracted_voice_id(input_file_id: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT voice_file_id FROM extract_cache WHERE input_file_id = ?", (input_file_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def save_extracted_voice_id(input_file_id: str, voice_file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO extract_cache (input_file_id, voice_file_id) VALUES (?, ?)", (input_file_id, voice_file_id))
        await db.commit()

async def get_chat_settings(chat_id: int, thread_id: int = 0) -> tuple[str, bool]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT mode, delete_links FROM chat_settings WHERE chat_id = ? AND thread_id = ?", (chat_id, thread_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0], bool(row[1])
            return "normal", False

async def set_chat_mode(chat_id: int, thread_id: int, mode: str):
    async with aiosqlite.connect(DB_PATH) as db:
        _, delete_links = await get_chat_settings(chat_id, thread_id)
        await db.execute(
            "INSERT OR REPLACE INTO chat_settings (chat_id, thread_id, mode, delete_links) VALUES (?, ?, ?, ?)",
            (chat_id, thread_id, mode, 1 if delete_links else 0)
        )
        await db.commit()

async def toggle_delete_links_setting(chat_id: int, thread_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        mode, current_delete_links = await get_chat_settings(chat_id, thread_id)
        new_status = not current_delete_links
        new_status_int = 1 if new_status else 0
        
        await db.execute(
            "INSERT OR REPLACE INTO chat_settings (chat_id, thread_id, mode, delete_links) VALUES (?, ?, ?, ?)",
            (chat_id, thread_id, mode, new_status_int)
        )
        await db.commit()
        return new_status

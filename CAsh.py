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

async def get_chat_settings(chat_id: int, thread_id: int = 0) -> tuple[str, bool]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT mode, delete_links FROM chat_settings WHERE chat_id = ? AND thread_id = ?", (chat_id, thread_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0], bool(row[1])
            return "normal", False

async def set_chat_mode(chat_id: int, thread_id: int, mode: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO chat_settings (chat_id, thread_id, mode, delete_links)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(chat_id, thread_id) DO UPDATE SET mode = excluded.mode
        """, (chat_id, thread_id, mode))
        await db.commit()

async def toggle_delete_links_setting(chat_id: int, thread_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        _, current_delete_links = await get_chat_settings(chat_id, thread_id)
        new_status = 0 if current_delete_links else 1
        
        await db.execute("""
            INSERT INTO chat_settings (chat_id, thread_id, mode, delete_links)
            VALUES (?, ?, 'normal', ?)
            ON CONFLICT(chat_id, thread_id) DO UPDATE SET delete_links = excluded.delete_links
        """, (chat_id, thread_id, new_status))
        await db.commit()
        
        return bool(new_status)

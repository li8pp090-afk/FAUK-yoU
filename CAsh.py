DB_PATH = "bot_data.db"


def init_db(sqlite3):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            mode TEXT DEFAULT 'normal'
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_cache (
            url TEXT PRIMARY KEY,
            file_id TEXT,
            file_type TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_mode(sqlite3, key: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT mode FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "normal"


def set_mode(sqlite3, key: str, mode: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO settings (key, mode) VALUES (?, ?)", (key, mode)
    )
    conn.commit()
    conn.close()


def get_cached_file(sqlite3, url: str, file_type: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT file_id FROM file_cache WHERE url = ? AND file_type = ?",
        (url, file_type)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def save_cached_file(sqlite3, url: str, file_id: str, file_type: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO file_cache (url, file_id, file_type) VALUES (?, ?, ?)",
        (url, file_id, file_type)
    )
    conn.commit()
    conn.close()

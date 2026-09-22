import hashlib
import json
import aiosqlite

MAX_CONCURRENT_PER_USER = 3
QUEUE_SIZE_PER_USER = 3


async def create_pool(db_path):
    conn = await aiosqlite.connect(db_path, timeout=30.0)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL;")
    return conn


async def init_db(db):
    await db.executescript(
        """
        CREATE TABLE IF NOT EXISTS user_modes (
            user_id INTEGER PRIMARY KEY,
            mode TEXT NOT NULL CHECK (mode IN ('normal', 'voice'))
        );

        CREATE TABLE IF NOT EXISTS user_replies (
            user_id INTEGER PRIMARY KEY,
            reply_index INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            job_data TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS jobs_user_id_idx
        ON jobs (user_id, id);

        CREATE TABLE IF NOT EXISTS file_cache (
            cache_key TEXT PRIMARY KEY,
            file_id TEXT NOT NULL
        );
        """
    )
    await db.commit()


def file_cache_key(mode, url):
    return f"{mode}:{hashlib.sha256(url.encode()).hexdigest()}"


async def get_mode(db, user_id):
    async with db.execute(
        "SELECT mode FROM user_modes WHERE user_id = ?", (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
    return row["mode"] if row else "normal"


async def set_mode(db, user_id, mode):
    await db.execute(
        """
        INSERT INTO user_modes (user_id, mode)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET mode = excluded.mode
        """,
        (user_id, mode),
    )
    await db.commit()


async def get_reply_index(db, user_id, count):
    async with db.execute(
        "SELECT reply_index FROM user_replies WHERE user_id = ?", (user_id,)
    ) as cursor:
        row = await cursor.fetchone()

    index = row["reply_index"] % count if row else 0

    await db.execute(
        """
        INSERT INTO user_replies (user_id, reply_index)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET reply_index = excluded.reply_index
        """,
        (user_id, (index + 1) % count),
    )
    await db.commit()
    return index


async def get_cached_file(db, mode, url):
    async with db.execute(
        "SELECT file_id FROM file_cache WHERE cache_key = ?",
        (file_cache_key(mode, url),),
    ) as cursor:
        row = await cursor.fetchone()
    return row["file_id"] if row else None


async def set_cached_file(db, mode, url, file_id):
    await db.execute(
        """
        INSERT INTO file_cache (cache_key, file_id)
        VALUES (?, ?)
        ON CONFLICT(cache_key)
        DO UPDATE SET file_id = excluded.file_id
        """,
        (file_cache_key(mode, url), file_id),
    )
    await db.commit()


async def delete_cached_file(db, mode, url):
    await db.execute(
        "DELETE FROM file_cache WHERE cache_key = ?",
        (file_cache_key(mode, url),),
    )
    await db.commit()


async def push_job(db, user_id, job):
    async with db.execute(
        "SELECT COUNT(*) as cnt FROM jobs WHERE user_id = ?", (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
        count = row["cnt"] if row else 0

    if count >= QUEUE_SIZE_PER_USER:
        return False

    await db.execute(
        "INSERT INTO jobs (user_id, job_data) VALUES (?, ?)",
        (user_id, json.dumps(job, ensure_ascii=False)),
    )
    await db.commit()
    return True


async def pop_job(db, user_id):
    while True:
        async with db.execute(
            "SELECT id, job_data FROM jobs WHERE user_id = ? ORDER BY id ASC LIMIT 1",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            job_id = row["id"]
            job_data = row["job_data"]

            await db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            await db.commit()
            return json.loads(job_data)

        await asyncio.sleep(0.5)


async def clear_all_queues(db):
    await db.execute("DELETE FROM jobs")
    await db.commit()

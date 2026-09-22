import asyncio
import hashlib
import json


MAX_CONCURRENT_PER_USER = 3
QUEUE_SIZE_PER_USER = 3


async def create_pool(database_url):
    import asyncpg

    return await asyncpg.create_pool(
        database_url,
        min_size=1,
        max_size=10
    )


async def init_db(db):
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_modes (
            user_id BIGINT PRIMARY KEY,
            mode TEXT NOT NULL
                CHECK (mode IN ('normal', 'voice'))
        );

        CREATE TABLE IF NOT EXISTS user_replies (
            user_id BIGINT PRIMARY KEY,
            reply_index INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            job_data JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS jobs_user_id_idx
        ON jobs (user_id, id);

        CREATE TABLE IF NOT EXISTS file_cache (
            cache_key TEXT PRIMARY KEY,
            file_id TEXT NOT NULL
        );
        """
    )


def file_cache_key(mode, url):
    return (
        f"{mode}:"
        f"{hashlib.sha256(url.encode()).hexdigest()}"
    )


async def get_mode(db, user_id):
    row = await db.fetchrow(
        """
        SELECT mode
        FROM user_modes
        WHERE user_id = $1
        """,
        user_id
    )

    if not row:
        return "normal"

    return row["mode"]


async def set_mode(db, user_id, mode):
    await db.execute(
        """
        INSERT INTO user_modes (
            user_id,
            mode
        )
        VALUES ($1, $2)
        ON CONFLICT (user_id)
        DO UPDATE SET mode = EXCLUDED.mode
        """,
        user_id,
        mode
    )


async def get_reply_index(db, user_id, count):
    row = await db.fetchrow(
        """
        SELECT reply_index
        FROM user_replies
        WHERE user_id = $1
        """,
        user_id
    )

    index = 0

    if row:
        index = row["reply_index"] % count

    await db.execute(
        """
        INSERT INTO user_replies (
            user_id,
            reply_index
        )
        VALUES ($1, $2)
        ON CONFLICT (user_id)
        DO UPDATE SET reply_index = EXCLUDED.reply_index
        """,
        user_id,
        (index + 1) % count
    )

    return index


async def get_cached_file(db, mode, url):
    return await db.fetchval(
        """
        SELECT file_id
        FROM file_cache
        WHERE cache_key = $1
        """,
        file_cache_key(mode, url)
    )


async def set_cached_file(
    db,
    mode,
    url,
    file_id
):
    await db.execute(
        """
        INSERT INTO file_cache (
            cache_key,
            file_id
        )
        VALUES ($1, $2)
        ON CONFLICT (cache_key)
        DO UPDATE SET file_id = EXCLUDED.file_id
        """,
        file_cache_key(mode, url),
        file_id
    )


async def delete_cached_file(
    db,
    mode,
    url
):
    await db.execute(
        """
        DELETE FROM file_cache
        WHERE cache_key = $1
        """,
        file_cache_key(mode, url)
    )


async def push_job(db, user_id, job):
    async with db.acquire() as conn:
        async with conn.transaction():
            count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM jobs
                WHERE user_id = $1
                """,
                user_id
            )

            if count >= QUEUE_SIZE_PER_USER:
                return False

            await conn.execute(
                """
                INSERT INTO jobs (
                    user_id,
                    job_data
                )
                VALUES ($1, $2::jsonb)
                """,
                user_id,
                json.dumps(
                    job,
                    ensure_ascii=False
                )
            )

            return True


async def pop_job(db, user_id):
    while True:
        async with db.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT id, job_data
                    FROM jobs
                    WHERE user_id = $1
                    ORDER BY id
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """,
                    user_id
                )

                if row:
                    await conn.execute(
                        """
                        DELETE FROM jobs
                        WHERE id = $1
                        """,
                        row["id"]
                    )

                    return json.loads(
                        row["job_data"]
                    )

        await asyncio.sleep(0.2)


async def clear_all_queues(db):
    await db.execute(
        """
        DELETE FROM jobs
        """
    )
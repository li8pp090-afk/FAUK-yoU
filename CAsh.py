import time

import aiosqlite


DB_PATH = "bot.db"

DEFAULT_MODE = "voice"

MAX_ACTIVE_DOWNLOADS = 3
MAX_QUEUED_DOWNLOADS = 3

PRIVATE_SCOPE_PREFIX = "private:"

VALID_MODES = {
    "voice",
    "virtual"
}

VALID_FILE_TYPES = {
    "video",
    "document",
    "voice",
    "photo",
    "video_note"
}


def is_private_scope(scope_id):
    return (
        isinstance(scope_id, str)
        and scope_id.startswith(PRIVATE_SCOPE_PREFIX)
    )


def normalize_private_scope(scope_id):
    if not is_private_scope(scope_id):
        return None

    return scope_id


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "PRAGMA foreign_keys = ON"
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_modes (
                scope_id TEXT PRIMARY KEY,
                mode TEXT NOT NULL
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS edit_button_permissions (
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY (
                    chat_id,
                    message_id
                )
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS reply_states (
                user_id INTEGER PRIMARY KEY,
                reply_index INTEGER NOT NULL
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS file_cache (
                cache_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT NOT NULL UNIQUE,
                source_url TEXT NOT NULL,
                mode TEXT NOT NULL,
                scope_id TEXT,
                created_at REAL NOT NULL
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS file_cache_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_id INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                file_id TEXT NOT NULL,
                media_group_id TEXT,
                item_index INTEGER NOT NULL,
                FOREIGN KEY (
                    cache_id
                )
                REFERENCES file_cache (
                    cache_id
                )
                ON DELETE CASCADE
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS download_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scope_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                message_thread_id INTEGER,
                source_url TEXT NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at REAL NOT NULL
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS voice_edit_sessions (
                user_id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                file_id TEXT NOT NULL
            )
            """
        )

        columns = []

        async with db.execute(
            "PRAGMA table_info(download_queue)"
        ) as cursor:
            async for row in cursor:
                columns.append(row[1])

        if "chat_id" not in columns:
            await db.execute(
                """
                ALTER TABLE download_queue
                ADD COLUMN chat_id INTEGER
                """
            )

        if "message_id" not in columns:
            await db.execute(
                """
                ALTER TABLE download_queue
                ADD COLUMN message_id INTEGER
                """
            )

        if "message_thread_id" not in columns:
            await db.execute(
                """
                ALTER TABLE download_queue
                ADD COLUMN message_thread_id INTEGER
                """
            )

        cache_columns = []

        async with db.execute(
            "PRAGMA table_info(file_cache)"
        ) as cursor:
            async for row in cursor:
                cache_columns.append(row[1])

        if "scope_id" not in cache_columns:
            await db.execute(
                """
                ALTER TABLE file_cache
                ADD COLUMN scope_id TEXT
                """
            )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_queue_scope_status
            ON download_queue (
                scope_id,
                status
            )
            """
        )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cache_key
            ON file_cache (
                cache_key
            )
            """
        )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cache_scope
            ON file_cache (
                scope_id
            )
            """
        )

        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_cache_items_cache
            ON file_cache_items (
                cache_id,
                item_index
            )
            """
        )

        await db.commit()


async def get_mode(scope_id):
    scope_id = normalize_private_scope(scope_id)

    if scope_id is None:
        return DEFAULT_MODE

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT mode
            FROM bot_modes
            WHERE scope_id = ?
            """,
            (scope_id,)
        )

        row = await cursor.fetchone()

        if row is None:
            return DEFAULT_MODE

        if row[0] not in VALID_MODES:
            return DEFAULT_MODE

        return row[0]


async def set_mode(
    scope_id,
    mode
):
    scope_id = normalize_private_scope(scope_id)

    if scope_id is None:
        return

    if mode not in VALID_MODES:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO bot_modes (
                scope_id,
                mode
            )
            VALUES (?, ?)
            ON CONFLICT(scope_id)
            DO UPDATE SET mode = excluded.mode
            """,
            (
                scope_id,
                mode
            )
        )

        await db.commit()


async def save_edit_permission(
    chat_id,
    message_id,
    user_id
):
    if not isinstance(chat_id, int):
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO edit_button_permissions (
                chat_id,
                message_id,
                user_id
            )
            VALUES (?, ?, ?)
            """,
            (
                chat_id,
                message_id,
                user_id
            )
        )

        await db.commit()


async def is_edit_button_owner(
    chat_id,
    message_id,
    user_id
):
    if not isinstance(chat_id, int):
        return False

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT 1
            FROM edit_button_permissions
            WHERE chat_id = ?
            AND message_id = ?
            AND user_id = ?
            """,
            (
                chat_id,
                message_id,
                user_id
            )
        )

        row = await cursor.fetchone()

        return row is not None


async def get_next_reply(
    user_id,
    replies_count
):
    if replies_count <= 0:
        return 0

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT reply_index
            FROM reply_states
            WHERE user_id = ?
            """,
            (user_id,)
        )

        row = await cursor.fetchone()

        if row is None:
            index = 0
        else:
            index = (
                row[0] + 1
            ) % replies_count

        await db.execute(
            """
            INSERT INTO reply_states (
                user_id,
                reply_index
            )
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET reply_index = excluded.reply_index
            """,
            (
                user_id,
                index
            )
        )

        await db.commit()

        return index


def build_cache_key(
    source_url,
    mode,
    scope_id
):
    scope_id = normalize_private_scope(scope_id)

    if scope_id is None:
        return None

    return f"{scope_id}:{mode}:{source_url}"


async def get_file_cache(
    source_url,
    mode,
    scope_id
):
    scope_id = normalize_private_scope(scope_id)

    if scope_id is None:
        return None

    cache_key = build_cache_key(
        source_url,
        mode,
        scope_id
    )

    if cache_key is None:
        return None

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT
                cache_id,
                cache_key,
                source_url,
                mode,
                scope_id,
                created_at
            FROM file_cache
            WHERE cache_key = ?
            AND scope_id = ?
            """,
            (
                cache_key,
                scope_id
            )
        )

        cache = await cursor.fetchone()

        if cache is None:
            return None

        cursor = await db.execute(
            """
            SELECT
                item_id,
                file_type,
                file_id,
                media_group_id,
                item_index
            FROM file_cache_items
            WHERE cache_id = ?
            ORDER BY item_index
            """,
            (cache[0],)
        )

        items = await cursor.fetchall()

        if not items:
            return None

        return {
            "cache_id": cache[0],
            "cache_key": cache[1],
            "source_url": cache[2],
            "mode": cache[3],
            "scope_id": cache[4],
            "created_at": cache[5],
            "items": [
                {
                    "item_id": row[0],
                    "file_type": row[1],
                    "file_id": row[2],
                    "media_group_id": row[3],
                    "item_index": row[4]
                }
                for row in items
            ]
        }


async def create_file_cache(
    source_url,
    mode,
    created_at,
    scope_id
):
    scope_id = normalize_private_scope(scope_id)

    if scope_id is None:
        return None

    cache_key = build_cache_key(
        source_url,
        mode,
        scope_id
    )

    if cache_key is None:
        return None

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            INSERT OR IGNORE INTO file_cache (
                cache_key,
                source_url,
                mode,
                scope_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cache_key,
                source_url,
                mode,
                scope_id,
                created_at
            )
        )

        await db.commit()

        if cursor.lastrowid:
            return cursor.lastrowid

        cursor = await db.execute(
            """
            SELECT cache_id
            FROM file_cache
            WHERE cache_key = ?
            AND scope_id = ?
            """,
            (
                cache_key,
                scope_id
            )
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return row[0]


async def save_file_cache_items(
    cache_id,
    items
):
    if not items:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT scope_id
            FROM file_cache
            WHERE cache_id = ?
            """,
            (cache_id,)
        )

        cache = await cursor.fetchone()

        if cache is None:
            return

        if not is_private_scope(cache[0]):
            return

        for item in items:
            if item["file_type"] not in VALID_FILE_TYPES:
                continue

            await db.execute(
                """
                INSERT OR REPLACE INTO file_cache_items (
                    item_id,
                    cache_id,
                    file_type,
                    file_id,
                    media_group_id,
                    item_index
                )
                VALUES (
                    COALESCE(
                        (
                            SELECT item_id
                            FROM file_cache_items
                            WHERE cache_id = ?
                            AND item_index = ?
                        ),
                        NULL
                    ),
                    ?, ?, ?, ?, ?
                )
                """,
                (
                    cache_id,
                    item["item_index"],
                    cache_id,
                    item["file_type"],
                    item["file_id"],
                    item.get("media_group_id"),
                    item["item_index"]
                )
            )

        await db.commit()


async def delete_file_cache(
    source_url,
    mode,
    scope_id
):
    scope_id = normalize_private_scope(scope_id)

    if scope_id is None:
        return

    cache_key = build_cache_key(
        source_url,
        mode,
        scope_id
    )

    if cache_key is None:
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            DELETE FROM file_cache
            WHERE cache_key = ?
            AND scope_id = ?
            """,
            (
                cache_key,
                scope_id
            )
        )

        await db.commit()


async def set_voice_edit_session(
    user_id,
    chat_id,
    message_id,
    file_id
):
    if not isinstance(chat_id, int):
        return

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO voice_edit_sessions (
                user_id,
                chat_id,
                message_id,
                file_id
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET
                chat_id = excluded.chat_id,
                message_id = excluded.message_id,
                file_id = excluded.file_id
            """,
            (
                user_id,
                chat_id,
                message_id,
                file_id
            )
        )

        await db.commit()


async def get_voice_edit_session(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT
                chat_id,
                message_id,
                file_id
            FROM voice_edit_sessions
            WHERE user_id = ?
            """,
            (user_id,)
        )

        row = await cursor.fetchone()

        if row is None:
            return None

        return {
            "chat_id": row[0],
            "message_id": row[1],
            "file_id": row[2]
        }


async def delete_voice_edit_session(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            DELETE FROM voice_edit_sessions
            WHERE user_id = ?
            """,
            (user_id,)
        )

        await db.commit()


async def add_download(
    scope_id,
    user_id,
    chat_id,
    message_id,
    message_thread_id,
    source_url,
    mode
):
    scope_id = normalize_private_scope(scope_id)

    if scope_id is None:
        return None

    if mode not in VALID_MODES:
        return None

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "BEGIN IMMEDIATE"
        )

        cursor = await db.execute(
            """
            SELECT COUNT(*)
            FROM download_queue
            WHERE scope_id = ?
            AND status = 'active'
            """,
            (scope_id,)
        )

        active_count = (
            await cursor.fetchone()
        )[0]

        cursor = await db.execute(
            """
            SELECT COUNT(*)
            FROM download_queue
            WHERE scope_id = ?
            AND status = 'queued'
            """,
            (scope_id,)
        )

        queued_count = (
            await cursor.fetchone()
        )[0]

        if active_count < MAX_ACTIVE_DOWNLOADS:
            status = "active"
        elif queued_count < MAX_QUEUED_DOWNLOADS:
            status = "queued"
        else:
            await db.rollback()
            return None

        cursor = await db.execute(
            """
            INSERT INTO download_queue (
                scope_id,
                user_id,
                chat_id,
                message_id,
                message_thread_id,
                source_url,
                mode,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scope_id,
                user_id,
                chat_id,
                message_id,
                message_thread_id,
                source_url,
                mode,
                status,
                time.time()
            )
        )

        job_id = cursor.lastrowid

        await db.commit()

        return {
            "id": job_id,
            "scope_id": scope_id,
            "user_id": user_id,
            "chat_id": chat_id,
            "message_id": message_id,
            "message_thread_id": message_thread_id,
            "source_url": source_url,
            "mode": mode,
            "status": status
        }


async def get_next_queued_download(scope_id):
    scope_id = normalize_private_scope(scope_id)

    if scope_id is None:
        return None

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "BEGIN IMMEDIATE"
        )

        cursor = await db.execute(
            """
            SELECT COUNT(*)
            FROM download_queue
            WHERE scope_id = ?
            AND status = 'active'
            """,
            (scope_id,)
        )

        active_count = (
            await cursor.fetchone()
        )[0]

        if active_count >= MAX_ACTIVE_DOWNLOADS:
            await db.rollback()
            return None

        cursor = await db.execute(
            """
            SELECT
                id,
                scope_id,
                user_id,
                chat_id,
                message_id,
                message_thread_id,
                source_url,
                mode
            FROM download_queue
            WHERE scope_id = ?
            AND status = 'queued'
            ORDER BY created_at, id
            LIMIT 1
            """,
            (scope_id,)
        )

        row = await cursor.fetchone()

        if row is None:
            await db.rollback()
            return None

        await db.execute(
            """
            UPDATE download_queue
            SET status = 'active'
            WHERE id = ?
            """,
            (row[0],)
        )

        await db.commit()

        return {
            "id": row[0],
            "scope_id": row[1],
            "user_id": row[2],
            "chat_id": row[3],
            "message_id": row[4],
            "message_thread_id": row[5],
            "source_url": row[6],
            "mode": row[7],
            "status": "active"
        }


async def finish_download(job_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            DELETE FROM download_queue
            WHERE id = ?
            """,
            (job_id,)
        )

        await db.commit()


async def fail_download(job_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            DELETE FROM download_queue
            WHERE id = ?
            """,
            (job_id,)
        )

        await db.commit()
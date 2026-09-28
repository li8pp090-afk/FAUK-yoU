import aiosqlite


DB_PATH = "bot.db"
db = None


async def init_db():
    global db

    db = await aiosqlite.connect(
        DB_PATH
    )

    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS file_ids (
            file_key TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            file_unique_id TEXT,
            filename TEXT
        )
    """)

    await db.commit()


async def close_db():
    global db

    if db:
        await db.close()
        db = None


async def recover_stale_tasks():
    await db.execute("""
        UPDATE tasks
        SET status = 'abandoned'
        WHERE status IN (
            'queued',
            'active',
            'downloading',
            'sending'
        )
    """)

    await db.commit()


async def add_user(user_id):
    await db.execute(
        """
        INSERT OR IGNORE INTO users (
            user_id
        )
        VALUES (?)
        """,
        (user_id,)
    )

    await db.commit()


async def add_task(
    task_id,
    user_id,
    status
):
    await db.execute(
        """
        INSERT INTO tasks (
            task_id,
            user_id,
            status
        )
        VALUES (?, ?, ?)
        """,
        (
            task_id,
            user_id,
            status
        )
    )

    await db.commit()


async def update_task(
    task_id,
    status
):
    await db.execute(
        """
        UPDATE tasks
        SET status = ?
        WHERE task_id = ?
        """,
        (
            status,
            task_id
        )
    )

    await db.commit()


async def delete_task(task_id):
    await db.execute(
        """
        DELETE FROM tasks
        WHERE task_id = ?
        """,
        (task_id,)
    )

    await db.commit()


async def save_file_id(
    file_key,
    file_id,
    file_unique_id,
    filename
):
    await db.execute(
        """
        INSERT OR REPLACE INTO file_ids (
            file_key,
            file_id,
            file_unique_id,
            filename
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            file_key,
            file_id,
            file_unique_id,
            filename
        )
    )

    await db.commit()


async def get_file_id(file_key):
    cursor = await db.execute(
        """
        SELECT
            file_id,
            file_unique_id,
            filename
        FROM file_ids
        WHERE file_key = ?
        """,
        (file_key,)
    )

    row = await cursor.fetchone()

    await cursor.close()

    return row


async def delete_file_id(file_key):
    await db.execute(
        """
        DELETE FROM file_ids
        WHERE file_key = ?
        """,
        (file_key,)
    )

    await db.commit()
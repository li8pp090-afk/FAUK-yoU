import aiosqlite


DB_PATH = "bot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_modes (
                scope_id TEXT PRIMARY KEY,
                mode TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS edit_button_permissions (
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY (chat_id, message_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reply_states (
                scope_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                reply_index INTEGER NOT NULL,
                PRIMARY KEY (scope_id, user_id)
            )
        """)

        await db.commit()


async def get_mode(scope_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT mode FROM bot_modes WHERE scope_id = ?",
            (scope_id,)
        )
        row = await cursor.fetchone()

    if row is None:
        return "voice"

    return row[0]


async def set_mode(scope_id, mode):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO bot_modes (scope_id, mode)
            VALUES (?, ?)
            ON CONFLICT(scope_id)
            DO UPDATE SET mode = excluded.mode
            """,
            (scope_id, mode)
        )
        await db.commit()


async def save_edit_permission(chat_id, message_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO edit_button_permissions
            (chat_id, message_id, user_id)
            VALUES (?, ?, ?)
            """,
            (chat_id, message_id, user_id)
        )
        await db.commit()


async def get_edit_permission(chat_id, message_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT user_id
            FROM edit_button_permissions
            WHERE chat_id = ? AND message_id = ?
            """,
            (chat_id, message_id)
        )
        row = await cursor.fetchone()

    return row[0] if row else None


async def is_edit_button_owner(chat_id, message_id, user_id):
    owner_id = await get_edit_permission(
        chat_id,
        message_id
    )

    return owner_id == user_id


async def get_next_reply(scope_id, user_id, replies_count):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            SELECT reply_index
            FROM reply_states
            WHERE scope_id = ? AND user_id = ?
            """,
            (scope_id, user_id)
        )

        row = await cursor.fetchone()

        if row is None:
            next_index = 0
        else:
            next_index = (row[0] + 1) % replies_count

        await db.execute(
            """
            INSERT INTO reply_states
            (scope_id, user_id, reply_index)
            VALUES (?, ?, ?)
            ON CONFLICT(scope_id, user_id)
            DO UPDATE SET reply_index = excluded.reply_index
            """,
            (scope_id, user_id, next_index)
        )

        await db.commit()

    return next_index
import aiosqlite
from aiogram import F, Router
from aiogram.enums import ButtonStyle, ChatMemberStatus
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from Reply import MESSAGES


BUTTON_TEXTS = {
    "btn_voice": "فويس",
    "btn_default": "افتراضي",
    "btn_notice_lock": "قفل الاشعارات",
    "btn_notice_open": "فتح الاشعارات",
    "edit_mode_text": "تستطيع تغيير وضع عمل البوت\nمن هنا",
    "unauthorized": "عزيزي\nليس مصرح لك بذلك",
}


def scope_for_message(message: Message) -> str:
    if message.chat.type == "private":
        return f"user:{message.from_user.id}"

    thread_id = getattr(message, "message_thread_id", None)
    if thread_id:
        return f"chat:{message.chat.id}:topic:{thread_id}"

    return f"chat:{message.chat.id}"


def scope_for_callback(callback: CallbackQuery) -> str:
    if not callback.message:
        return f"user:{callback.from_user.id}"

    if callback.message.chat.type == "private":
        return f"user:{callback.from_user.id}"

    thread_id = getattr(callback.message, "message_thread_id", None)
    if thread_id:
        return f"chat:{callback.message.chat.id}:topic:{thread_id}"

    return f"chat:{callback.message.chat.id}"


async def init_settings_db(db_path: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                scope_key TEXT PRIMARY KEY,
                mode TEXT NOT NULL DEFAULT 'default',
                notice_state TEXT NOT NULL DEFAULT 'disabled'
            )
            """
        )
        await db.commit()


async def ensure_scope(db, scope: str):
    await db.execute(
        """
        INSERT OR IGNORE INTO settings (
            scope_key,
            mode,
            notice_state
        )
        VALUES (?, 'default', 'disabled')
        """,
        (scope,),
    )


async def get_mode(db_path: str, scope: str) -> str:
    async with aiosqlite.connect(db_path) as db:
        await ensure_scope(db, scope)
        await db.commit()

        cursor = await db.execute(
            "SELECT mode FROM settings WHERE scope_key = ?",
            (scope,),
        )
        row = await cursor.fetchone()

    return row[0]


async def set_mode(db_path: str, scope: str, mode: str):
    async with aiosqlite.connect(db_path) as db:
        await ensure_scope(db, scope)

        await db.execute(
            """
            UPDATE settings
            SET mode = ?
            WHERE scope_key = ?
            """,
            (mode, scope),
        )
        await db.commit()


async def get_notice_state(db_path: str, scope: str) -> str:
    async with aiosqlite.connect(db_path) as db:
        await ensure_scope(db, scope)
        await db.commit()

        cursor = await db.execute(
            "SELECT notice_state FROM settings WHERE scope_key = ?",
            (scope,),
        )
        row = await cursor.fetchone()

    return row[0]


async def set_notice_state(db_path: str, scope: str, state: str):
    async with aiosqlite.connect(db_path) as db:
        await ensure_scope(db, scope)

        await db.execute(
            """
            UPDATE settings
            SET notice_state = ?
            WHERE scope_key = ?
            """,
            (state, scope),
        )
        await db.commit()


def settings_markup(
    mode: str,
    notice_state: str,
) -> InlineKeyboardMarkup:
    notice_enabled = notice_state == "enabled"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BUTTON_TEXTS["btn_voice"],
                    callback_data="mode:voice",
                    style=(
                        ButtonStyle.PRIMARY
                        if mode == "voice"
                        else ButtonStyle.DANGER
                    ),
                ),
                InlineKeyboardButton(
                    text=BUTTON_TEXTS["btn_default"],
                    callback_data="mode:default",
                    style=(
                        ButtonStyle.PRIMARY
                        if mode == "default"
                        else ButtonStyle.DANGER
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text=(
                        BUTTON_TEXTS["btn_notice_lock"]
                        if notice_enabled
                        else BUTTON_TEXTS["btn_notice_open"]
                    ),
                    callback_data=(
                        "notice:disable"
                        if notice_enabled
                        else "notice:enable"
                    ),
                    style=(
                        ButtonStyle.PRIMARY
                        if notice_enabled
                        else ButtonStyle.DANGER
                    ),
                ),
            ],
        ]
    )


async def is_admin(message: Message) -> bool:
    if message.chat.type == "private":
        return True

    if not message.from_user:
        return False

    try:
        member = await message.bot.get_chat_member(
            message.chat.id,
            message.from_user.id,
        )
        return member.status in {
            ChatMemberStatus.CREATOR,
            ChatMemberStatus.ADMINISTRATOR,
        }
    except Exception:
        return False


async def is_callback_admin(callback: CallbackQuery) -> bool:
    if not callback.message:
        return False

    if callback.message.chat.type == "private":
        return True

    try:
        member = await callback.bot.get_chat_member(
            callback.message.chat.id,
            callback.from_user.id,
        )
        return member.status in {
            ChatMemberStatus.CREATOR,
            ChatMemberStatus.ADMINISTRATOR,
        }
    except Exception:
        return False


def setup_button_handlers(db_path: str):
    router = Router(name="button_router")

    @router.message(F.text == "ادت")
    async def edit_mode(message: Message):
        if not await is_admin(message):
            return

        scope = scope_for_message(message)
        mode = await get_mode(db_path, scope)
        notice_state = await get_notice_state(db_path, scope)

        await message.reply(
            BUTTON_TEXTS["edit_mode_text"],
            reply_markup=settings_markup(
                mode,
                notice_state,
            ),
        )

    @router.callback_query(F.data.startswith("mode:"))
    async def mode_callback(callback: CallbackQuery):
        if not callback.message:
            await callback.answer()
            return

        if not await is_callback_admin(callback):
            await callback.answer(
                BUTTON_TEXTS["unauthorized"],
                show_alert=True,
            )
            return

        requested = callback.data.split(":", 1)[1]
        scope = scope_for_callback(callback)
        current = await get_mode(db_path, scope)

        if requested == current:
            requested = (
                "voice"
                if current == "default"
                else "default"
            )

        await set_mode(db_path, scope, requested)
        notice_state = await get_notice_state(db_path, scope)

        await callback.message.edit_reply_markup(
            reply_markup=settings_markup(
                requested,
                notice_state,
            )
        )

        await callback.answer()

    @router.callback_query(F.data.startswith("notice:"))
    async def notice_callback(callback: CallbackQuery):
        if not callback.message:
            await callback.answer()
            return

        if not await is_callback_admin(callback):
            await callback.answer(
                BUTTON_TEXTS["unauthorized"],
                show_alert=True,
            )
            return

        action = callback.data.split(":", 1)[1]
        scope = scope_for_callback(callback)
        new_state = (
            "enabled"
            if action == "enable"
            else "disabled"
        )

        await set_notice_state(db_path, scope, new_state)
        current_mode = await get_mode(db_path, scope)

        await callback.message.edit_reply_markup(
            reply_markup=settings_markup(
                current_mode,
                new_state,
            )
        )

        message_key = (
            "notice_enabled"
            if new_state == "enabled"
            else "notice_disabled"
        )

        await callback.answer(
            MESSAGES[message_key],
            show_alert=True,
        )

    return router

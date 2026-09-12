import aiosqlite
from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

BUTTON_TEXTS = {
    "btn_voice": "فويس",
    "btn_default": "افتراضي",
    "edit_mode_text": "تستطيع تغيير وضع عمل البوت\nمن هنا",
    "unauthorized": "عزيزي\nليس مصرح لك بذلك",
}

button_router = Router()

def settings_markup(mode: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=BUTTON_TEXTS["btn_voice"],
                callback_data="mode:voice",
                style="primary" if mode == "voice" else "danger",
            ),
            InlineKeyboardButton(
                text=BUTTON_TEXTS["btn_default"],
                callback_data="mode:default",
                style="primary" if mode == "default" else "danger",
            ),
        ]]
    )

def scope_for_message(message: Message) -> str:
    if message.chat.type == "private":
        return f"user:{message.from_user.id}"
    if message.message_thread_id:
        return f"chat:{message.chat.id}:topic:{message.message_thread_id}"
    return f"chat:{message.chat.id}"

def scope_for_callback(callback: CallbackQuery) -> str:
    if callback.message and callback.message.chat.type == "private":
        return f"user:{callback.from_user.id}"
    if callback.message and callback.message.message_thread_id:
        return f"chat:{callback.message.chat.id}:topic:{callback.message.message_thread_id}"
    if callback.message:
        return f"chat:{callback.message.chat.id}"
    return f"user:{callback.from_user.id}"

async def get_mode(db_path: str, scope: str) -> str:
    async with aiosqlite.connect(db_path) as db:
        cur = await db.execute(
            "SELECT mode FROM settings WHERE scope_key = ?", (scope,)
        )
        row = await cur.fetchone()
        return row[0] if row else "default"

async def set_mode(db_path: str, scope: str, mode: str):
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO settings(scope_key, mode)
            VALUES (?, ?)
            ON CONFLICT(scope_key)
            DO UPDATE SET mode = excluded.mode
        """,
            (scope, mode),
        )
        await db.commit()

async def is_admin(message: Message) -> bool:
    if message.chat.type == "private":
        return True
    if not message.from_user:
        return False
    try:
        member = await message.bot.get_chat_member(
            message.chat.id, message.from_user.id
        )
        return member.status in ("creator", "administrator")
    except Exception:
        return False

async def is_callback_admin(callback: CallbackQuery) -> bool:
    if not callback.message:
        return False
    if callback.message.chat.type == "private":
        return True
    try:
        member = await callback.bot.get_chat_member(
            callback.message.chat.id, callback.from_user.id
        )
        return member.status in ("creator", "administrator")
    except Exception:
        return False

def setup_button_handlers(db_path: str):
    @button_router.message(F.text == "ادت")
    async def edit_mode(message: Message):
        if not await is_admin(message):
            return
        scope = scope_for_message(message)
        mode = await get_mode(db_path, scope)
        await message.reply(
            BUTTON_TEXTS["edit_mode_text"],
            reply_markup=settings_markup(mode),
        )

    @button_router.callback_query(F.data.startswith("mode:"))
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
            requested = "voice" if current == "default" else "default"

        await set_mode(db_path, scope, requested)
        await callback.message.edit_reply_markup(
            reply_markup=settings_markup(requested)
        )
        await callback.answer()

    return button_router

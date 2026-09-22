from aiogram import F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from CAsh import get_mode, set_mode
from Reply import BUTTON_TEXTS, COMMAND_EDIT_MODE


def scope_for_message(message: Message) -> str:
    if message.chat.type == "private":
        return f"user:{message.chat.id}"

    thread_id = getattr(
        message,
        "message_thread_id",
        None,
    )

    if thread_id:
        return (
            f"chat:{message.chat.id}:"
            f"topic:{thread_id}"
        )

    return f"chat:{message.chat.id}"


def scope_for_callback(
    callback: CallbackQuery,
) -> str:
    if not callback.message:
        return f"user:{callback.from_user.id}"

    return scope_for_message(
        callback.message
    )


def settings_markup(
    mode: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BUTTON_TEXTS["btn_voice"],
                    callback_data="mode:voice",
                ),
                InlineKeyboardButton(
                    text=BUTTON_TEXTS["btn_default"],
                    callback_data="mode:default",
                ),
            ]
        ]
    )


async def is_admin(
    message: Message,
) -> bool:
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
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        }

    except Exception:
        return False


def setup_button_handlers(
    db_path: str,
):
    router = Router(
        name="button_router"
    )

    @router.message(
        F.text == COMMAND_EDIT_MODE
    )
    async def edit_mode(
        message: Message,
    ):
        if not await is_admin(message):
            await message.answer(
                BUTTON_TEXTS["unauthorized"]
            )
            return

        scope = scope_for_message(
            message
        )

        mode = get_mode(
            db_path,
            scope,
        )

        await message.answer(
            BUTTON_TEXTS["edit_mode_text"],
            reply_markup=settings_markup(
                mode
            ),
        )

    @router.callback_query(
        F.data.startswith("mode:")
    )
    async def mode_callback(
        callback: CallbackQuery,
    ):
        if not callback.message:
            await callback.answer()
            return

        if not await is_admin(
            callback.message
        ):
            await callback.answer(
                BUTTON_TEXTS["unauthorized"],
                show_alert=True,
            )
            return

        requested = callback.data.split(
            ":",
            1,
        )[1]

        if requested not in {
            "voice",
            "default",
        }:
            await callback.answer()
            return

        scope = scope_for_callback(
            callback
        )

        set_mode(
            db_path,
            scope,
            requested,
        )

        await callback.message.edit_reply_markup(
            reply_markup=settings_markup(
                requested
            )
        )

        await callback.answer()

    return router
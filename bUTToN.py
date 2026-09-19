from aiogram import F
from aiogram import Dispatcher
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from Reply import (
    UNAUTHORIZED,
    VOICE_BUTTON,
    VIRTUAL_BUTTON
)

from CAsh import (
    get_mode,
    set_mode,
    is_edit_button_owner
)


def mode_keyboard(current_mode):
    if current_mode == "voice":
        voice_style = "primary"
        virtual_style = "danger"
    else:
        voice_style = "danger"
        virtual_style = "primary"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=VOICE_BUTTON,
                    callback_data="mode:voice",
                    style=voice_style
                ),
                InlineKeyboardButton(
                    text=VIRTUAL_BUTTON,
                    callback_data="mode:virtual",
                    style=virtual_style
                )
            ]
        ]
    )


async def mode_callback(callback: CallbackQuery):
    if callback.message is None:
        return

    if not await is_edit_button_owner(
        callback.message.chat.id,
        callback.message.message_id,
        callback.from_user.id
    ):
        await callback.answer(
            UNAUTHORIZED,
            show_alert=True
        )
        return

    requested_mode = callback.data.split(":", 1)[1]

    if requested_mode not in {"voice", "virtual"}:
        await callback.answer()
        return

    if callback.message.chat.type == "private":
        scope_id = f"private:{callback.from_user.id}"
    else:
        scope_id = f"chat:{callback.message.chat.id}"

    current_mode = await get_mode(scope_id)

    if requested_mode == current_mode:
        new_mode = "virtual" if current_mode == "voice" else "voice"
    else:
        new_mode = requested_mode

    await set_mode(scope_id, new_mode)

    await callback.message.edit_reply_markup(
        reply_markup=mode_keyboard(new_mode)
    )

    await callback.answer()


def register_button_handlers(dp: Dispatcher):
    dp.callback_query.register(
        mode_callback,
        F.data.startswith("mode:")
    )
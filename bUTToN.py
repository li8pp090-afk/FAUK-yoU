from functools import partial

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from Reply import (
    VOICE_BUTTON,
    VOICE_EDIT_INFO,
    VIRTUAL_BUTTON
)

from CAsh import (
    get_mode,
    is_edit_button_owner,
    set_mode
)


VALID_MODES = {"voice", "virtual"}
PRIVATE_CHAT = "private"


def get_scope_id(message):
    if message.chat.type != PRIVATE_CHAT:
        return None

    thread_id = message.message_thread_id

    if thread_id:
        return (
            f"private:{message.chat.id}"
            f":topic:{thread_id}"
        )

    return f"private:{message.chat.id}"


def mode_keyboard(current_mode):
    voice_style = (
        "primary"
        if current_mode == "voice"
        else "danger"
    )

    virtual_style = (
        "primary"
        if current_mode == "virtual"
        else "danger"
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=VIRTUAL_BUTTON,
                    callback_data="mode:virtual",
                    style=virtual_style
                ),
                InlineKeyboardButton(
                    text=VOICE_BUTTON,
                    callback_data="mode:voice",
                    style=voice_style
                )
            ]
        ]
    )


def get_reversed_mode(current_mode):
    return (
        "virtual"
        if current_mode == "voice"
        else "voice"
    )


async def mode_callback(
    callback: CallbackQuery,
    bot: Bot
):
    message = callback.message

    if message is None:
        return

    if message.chat.type != PRIVATE_CHAT:
        return

    if not await is_edit_button_owner(
        message.chat.id,
        message.message_id,
        callback.from_user.id
    ):
        await callback.answer()
        return

    _, requested_mode = callback.data.split(
        ":",
        1
    )

    if requested_mode not in VALID_MODES:
        await callback.answer()
        return

    scope_id = get_scope_id(message)

    if scope_id is None:
        return

    current_mode = await get_mode(
        scope_id
    )

    new_mode = (
        get_reversed_mode(current_mode)
        if requested_mode == current_mode
        else requested_mode
    )

    await set_mode(
        scope_id,
        new_mode
    )

    await message.edit_reply_markup(
        reply_markup=mode_keyboard(
            new_mode
        )
    )

    await callback.answer()


async def voice_edit_info_callback(
    callback: CallbackQuery
):
    message = callback.message

    if message is None:
        return

    if message.chat.type != PRIVATE_CHAT:
        return

    await callback.answer(
        VOICE_EDIT_INFO,
        show_alert=True
    )


def register_button_handlers(
    dp: Dispatcher,
    bot: Bot
):
    dp.callback_query.register(
        partial(
            mode_callback,
            bot=bot
        ),
        F.data.startswith("mode:")
    )

    dp.callback_query.register(
        voice_edit_info_callback,
        F.data == "voice_edit_info"
    )
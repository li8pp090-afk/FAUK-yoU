from aiogram.enums import ButtonStyle
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from CAsh import get_mode, set_mode
from Reply import EDIT_TEXT, NORMAL_LABEL, VOICE_LABEL

MODE_NORMAL = "normal"
MODE_VOICE = "voice"


def scope_for_message(message):
    chat = message.chat

    if chat.type == "private":
        return f"user:{message.from_user.id}"

    thread_id = getattr(
        message,
        "message_thread_id",
        None,
    )

    if thread_id is not None:
        return f"chat:{chat.id}:topic:{thread_id}"

    return f"chat:{chat.id}"


def mode_keyboard(scope):
    mode = get_mode(scope)

    voice_style = (
        ButtonStyle.SUCCESS
        if mode == MODE_VOICE
        else ButtonStyle.DANGER
    )

    normal_style = (
        ButtonStyle.SUCCESS
        if mode == MODE_NORMAL
        else ButtonStyle.DANGER
    )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=VOICE_LABEL,
                    callback_data="mode:voice",
                    style=voice_style,
                ),
                InlineKeyboardButton(
                    text=NORMAL_LABEL,
                    callback_data="mode:normal",
                    style=normal_style,
                ),
            ]
        ]
    )


def change_mode(scope, requested_mode):
    current = get_mode(scope)

    if requested_mode == MODE_VOICE:
        new_mode = (
            MODE_NORMAL
            if current == MODE_VOICE
            else MODE_VOICE
        )
    else:
        new_mode = (
            MODE_VOICE
            if current == MODE_NORMAL
            else MODE_NORMAL
        )

    set_mode(
        scope,
        new_mode,
    )

    return new_mode
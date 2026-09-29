from aiogram.types import InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup

import Reply


DEVELOPER_STYLES = (
    "danger",
    "success",
    "primary",
)


def create_developer_button(
    developer_id,
    name,
    style,
):
    return InlineKeyboardButton(
        text=name,
        url=f"tg://user?id={developer_id}",
        style=style,
    )


def create_developer_markup(
    developer_id,
    name,
    style,
):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                create_developer_button(
                    developer_id,
                    name,
                    style,
                )
            ]
        ]
    )


def create_mode_markup(
    current_mode,
    developer_id=None,
    developer_name=None,
    developer_style=None,
):
    voice_style = (
        "success"
        if current_mode == "voice"
        else "danger"
    )

    normal_style = (
        "success"
        if current_mode == "normal"
        else "danger"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                text=Reply.MODE_VOICE,
                callback_data="mode:voice",
                style=voice_style,
            ),
            InlineKeyboardButton(
                text=Reply.MODE_NORMAL,
                callback_data="mode:normal",
                style=normal_style,
            ),
        ]
    ]

    if developer_id is not None:
        keyboard.append(
            [
                create_developer_button(
                    developer_id,
                    developer_name,
                    developer_style,
                )
            ]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=keyboard
    )
import random

from aiogram import F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

import Reply


_developer_pool = []


def _next_developer_id(takeoff_ids):
    global _developer_pool

    ids = list(dict.fromkeys(takeoff_ids))

    if not ids:
        return None

    if not _developer_pool or not set(_developer_pool).issubset(ids):
        _developer_pool = ids[:]
        random.shuffle(_developer_pool)

    developer_id = _developer_pool.pop()

    if not _developer_pool and len(ids) > 1:
        _developer_pool = ids[:]
        random.shuffle(_developer_pool)

        if _developer_pool[-1] == developer_id:
            swap_index = random.randrange(
                len(_developer_pool) - 1
            )
            _developer_pool[swap_index], _developer_pool[-1] = (
                _developer_pool[-1],
                _developer_pool[swap_index]
            )

    return developer_id


def mode_keyboard(mode):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=Reply.NORMAL_BUTTON,
                    callback_data="mode:normal",
                    style=(
                        "primary"
                        if mode == "normal"
                        else "danger"
                    )
                ),
                InlineKeyboardButton(
                    text=Reply.VOICE_BUTTON,
                    callback_data="mode:voice",
                    style=(
                        "primary"
                        if mode == "voice"
                        else "danger"
                    )
                )
            ]
        ]
    )


def takeoff_keyboard(takeoff_ids):
    developer_id = _next_developer_id(
        takeoff_ids
    )

    if developer_id is None:
        return None

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=Reply.DEVELOPER_BUTTON,
                    url=(
                        f"tg://user?id="
                        f"{developer_id}"
                    ),
                    style="success"
                )
            ]
        ]
    )


def register(
    dp,
    get_mode,
    set_mode
):
    @dp.message(
        F.text == Reply.EDIT_TRIGGER
    )
    async def edit_mode(message: Message):
        user_id = message.from_user.id
        mode = await get_mode(user_id)

        await message.answer(
            Reply.EDIT_MESSAGE,
            reply_markup=mode_keyboard(mode)
        )

    @dp.callback_query(
        F.data.startswith("mode:")
    )
    async def mode_callback(callback: CallbackQuery):
        user_id = callback.from_user.id
        current_mode = await get_mode(user_id)

        new_mode = (
            "voice"
            if current_mode == "normal"
            else "normal"
        )

        await set_mode(
            user_id,
            new_mode
        )

        await callback.message.edit_reply_markup(
            reply_markup=mode_keyboard(new_mode)
        )

        await callback.answer()